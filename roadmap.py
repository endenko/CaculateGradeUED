# -*- coding: utf-8 -*-
"""Graduation progress against one of the 68 CTĐT programs stored in hoc_phan.

The CSV is every course line extracted from the official program PDFs. It does
not mark electives, so progress is "listed credits matched", not a registrar's
required-versus-optional split.
"""
from __future__ import annotations

from utils import normalize

_PASSING = {"A+", "A", "B+", "B", "C+", "C", "D+", "D", "P"}
_FUZZY_MIN = 90


def _token_subset(left: str, right: str) -> bool:
    """True when one name is only a shorter piece of the other, such as Giải tích vs Giải tích hàm."""
    a = [tok for tok in left.split() if tok]
    b = [tok for tok in right.split() if tok]
    if not a or not b or len(a) == len(b):
        return False
    short, long = (a, b) if len(a) < len(b) else (b, a)
    return all(tok in long for tok in short)


def list_programs():
    import db
    conn = db.get_db()
    try:
        rows = conn.execute(
            """
            SELECT nganh, MIN(khoa) AS khoa, COUNT(*) AS so_mon,
                   COALESCE(SUM(tin_chi), 0) AS tin_chi
            FROM hoc_phan
            WHERE nganh IS NOT NULL AND nganh != '' AND nganh != 'Danh sách gốc (repo)'
            GROUP BY nganh
            ORDER BY khoa, nganh
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        {"nganh": r["nganh"], "khoa": r["khoa"], "so_mon": r["so_mon"], "tin_chi": int(r["tin_chi"] or 0)}
        for r in rows
    ]


def _program_courses(nganh: str):
    import db
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT ma_hp, ten_mon, tin_chi FROM hoc_phan WHERE nganh=? ORDER BY ten_mon, ma_hp",
            (nganh,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _letter(course: dict) -> str:
    return str(course.get("diem_he_4") or course.get("letter") or "").strip().upper()


def course_passed(course: dict) -> bool:
    """A listed attempt counts only when the real grade is a pass. Simulation is ignored."""
    if course.get("pass_only"):
        return True
    letter = _letter(course)
    if letter in _PASSING:
        return True
    if letter in {"F", "I", "X", "R"}:
        return False
    score = course.get("diem_10")
    if score not in (None, ""):
        try:
            return float(score) >= 4
        except (TypeError, ValueError):
            return False
    return False


def build_roadmap(nganh: str, courses) -> dict:
    required = _program_courses(nganh)
    if not required:
        return {"found": False, "nganh": nganh, "error": "Không thấy chương trình này trong cơ sở dữ liệu."}

    needed = []
    for index, row in enumerate(required):
        credits = int(row["tin_chi"] or 0)
        needed.append({
            "index": index,
            "ma_hp": row.get("ma_hp") or "",
            "ten_mon": row["ten_mon"],
            "tin_chi": credits,
            "norm": normalize(row["ten_mon"]),
            "code": str(row.get("ma_hp") or "").strip().lower(),
        })

    passed = [c for c in (courses or []) if isinstance(c, dict) and course_passed(c)]
    used_student = set()
    used_required = set()
    done = []

    def take(student_index, req, how, score):
        used_student.add(student_index)
        used_required.add(req["index"])
        done.append({
            "ma_hp": req["ma_hp"],
            "ten_mon": req["ten_mon"],
            "tin_chi": req["tin_chi"],
            "matched": (passed[student_index].get("ten_mon") or ""),
            "how": how,
            "score": score,
        })

    by_code = {}
    for req in needed:
        if req["code"]:
            by_code.setdefault(req["code"], []).append(req)
    by_name = {}
    for req in needed:
        by_name.setdefault(req["norm"], []).append(req)

    for index, course in enumerate(passed):
        code = str(course.get("ma_hp") or "").strip().lower()
        if not code:
            continue
        for req in by_code.get(code, []):
            if req["index"] not in used_required:
                take(index, req, "ma_hp", 100)
                break

    for index, course in enumerate(passed):
        if index in used_student:
            continue
        key = normalize(course.get("ten_mon") or "")
        if not key:
            continue
        for req in by_name.get(key, []):
            if req["index"] not in used_required:
                take(index, req, "ten", 100)
                break

    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None
    if fuzz is not None:
        pairs = []
        for index, course in enumerate(passed):
            if index in used_student:
                continue
            key = normalize(course.get("ten_mon") or "")
            if len(key) < 3:
                continue
            for req in needed:
                if req["index"] in used_required or _token_subset(key, req["norm"]):
                    continue
                score = max(fuzz.WRatio(key, req["norm"]), fuzz.token_set_ratio(key, req["norm"]))
                if score >= _FUZZY_MIN:
                    pairs.append((score, index, req))
        pairs.sort(key=lambda item: (-item[0], item[1], item[2]["index"]))
        for score, index, req in pairs:
            if index in used_student or req["index"] in used_required:
                continue
            take(index, req, "fuzzy", int(score))

    missing = [
        {"ma_hp": req["ma_hp"], "ten_mon": req["ten_mon"], "tin_chi": req["tin_chi"]}
        for req in needed if req["index"] not in used_required
    ]
    extra = [
        course.get("ten_mon") or ""
        for index, course in enumerate(passed) if index not in used_student
    ]
    required_credits = sum(req["tin_chi"] for req in needed)
    done_credits = sum(item["tin_chi"] for item in done)
    remaining = max(0, required_credits - done_credits)
    percent = round(100 * done_credits / required_credits) if required_credits else 0
    done.sort(key=lambda item: item["ten_mon"])
    missing.sort(key=lambda item: item["ten_mon"])
    return {
        "found": True,
        "nganh": nganh,
        "khoa": required and _khoa(nganh),
        "required_count": len(needed),
        "required_credits": required_credits,
        "done_count": len(done),
        "done_credits": done_credits,
        "remaining_credits": remaining,
        "missing_count": len(missing),
        "percent": percent,
        "done": done,
        "missing": missing,
        "extra": [name for name in extra if name],
        "note": "Danh sách là toàn bộ học phần trích từ file CTĐT của ngành, chưa tách môn tự chọn. Môn đạt khi điểm chữ từ D trở lên hoặc điểm P.",
    }


def _khoa(nganh: str) -> str:
    for program in list_programs():
        if program["nganh"] == nganh:
            return program["khoa"] or ""
    return ""
