# -*- coding: utf-8 -*-
"""Graduation progress against one of the 68 CTĐT programs stored in hoc_phan.

The CSV is every course line extracted from the official program PDFs. It does
not mark electives, so progress is "listed credits matched", not a registrar's
required-versus-optional split.
"""
from __future__ import annotations

import json
import os

from utils import normalize

_PASSING = {"A+", "A", "B+", "B", "C+", "C", "D+", "D", "P"}
_FUZZY_MIN = 90
_PLAN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ke_hoach_dao_tao.json")
_PLANS = None


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


def _score10(course: dict):
    for key in ("diem_10", "score10"):
        if course.get(key) not in (None, ""):
            return course.get(key)
    return None


def course_passed(course: dict) -> bool:
    """A listed attempt counts only when the real grade is a pass. Simulation is ignored."""
    if course.get("pass_only"):
        return True
    letter = _letter(course)
    if letter in _PASSING:
        return True
    if letter in {"F", "I", "X", "R"}:
        return False
    score = _score10(course)
    if score not in (None, ""):
        try:
            return float(score) >= 4
        except (TypeError, ValueError):
            return False
    return False


def course_in_progress(course: dict) -> bool:
    """Điểm học phần row with no final grade, or an OCR row still marked in progress."""
    if course_passed(course):
        return False
    if _letter(course) == "F":
        return False
    return bool(course.get("in_progress")) or (
        _letter(course) == "" and _score10(course) in (None, "") and course.get("source") == "bang2"
    )


def load_plans():
    global _PLANS
    if _PLANS is None:
        if os.path.exists(_PLAN_PATH):
            with open(_PLAN_PATH, encoding="utf-8") as handle:
                _PLANS = json.load(handle)
        else:
            _PLANS = {}
    return _PLANS


def _match_into(pool, needed, used_student, used_required, how_name, fuzzy):
    by_code = {}
    by_name = {}
    for req in needed:
        if req["code"]:
            by_code.setdefault(req["code"], []).append(req)
        by_name.setdefault(req["norm"], []).append(req)
    taken = []

    def take(student_index, req, how, score):
        used_student.add(student_index)
        used_required.add(req["index"])
        taken.append((student_index, req, how, score))

    for index, course in enumerate(pool):
        if index in used_student:
            continue
        code = str(course.get("ma_hp") or "").strip().lower()
        if not code:
            continue
        for req in by_code.get(code, []):
            if req["index"] not in used_required:
                take(index, req, "ma_hp", 100)
                break
    for index, course in enumerate(pool):
        if index in used_student:
            continue
        key = normalize(course.get("ten_mon") or "")
        if not key:
            continue
        for req in by_name.get(key, []):
            if req["index"] not in used_required:
                take(index, req, "ten", 100)
                break
    if fuzzy:
        try:
            from rapidfuzz import fuzz
        except ImportError:
            fuzz = None
        if fuzz is not None:
            pairs = []
            for index, course in enumerate(pool):
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
    return taken


def _outside_total(ma_hp, ten_mon, exclude):
    if not exclude:
        return False
    from ke_hoach import is_pe_or_defense
    return is_pe_or_defense(ma_hp, ten_mon)


def _completion(rows, plan):
    """Percent uses required courses plus the printed elective minimum, not every elective option."""
    exclude = bool(plan and plan.get("exclude_pe_qp"))
    required = [row for row in rows if row.get("loai") != "tu_chon" and not _outside_total(row.get("ma_hp"), row.get("ten_mon"), exclude)]
    elective = [row for row in rows if row.get("loai") == "tu_chon" and not _outside_total(row.get("ma_hp"), row.get("ten_mon"), exclude)]
    req_total = sum(int(row.get("tin_chi") or 0) for row in required)
    req_done = sum(int(row.get("tin_chi") or 0) for row in required if row.get("status") == "dat")
    ele_done = sum(int(row.get("tin_chi") or 0) for row in elective if row.get("status") == "dat")
    cap = None
    if plan:
        cap = plan.get("tu_chon_toi_thieu")
        if cap is None and plan.get("tin_chi_toi_thieu") and req_total:
            gap = int(plan["tin_chi_toi_thieu"]) - req_total
            if gap >= 0:
                cap = gap
    if cap is None:
        return req_done, req_total, ele_done, None, (round(100 * req_done / req_total) if req_total else 0)
    counted = min(int(cap), ele_done)
    total = req_total + int(cap)
    done = req_done + counted
    return req_done, req_total, counted, int(cap), (round(100 * done / total) if total else 0)


def build_roadmap(nganh: str, courses) -> dict:
    catalog = _program_courses(nganh)
    if not catalog:
        return {"found": False, "nganh": nganh, "error": "Không thấy chương trình này trong cơ sở dữ liệu."}
    plan = load_plans().get(nganh)
    by_code = {}
    for row in catalog:
        if row.get("ma_hp"):
            by_code.setdefault(str(row["ma_hp"]), row)
    planned = {}
    if plan:
        for item in plan.get("courses") or []:
            planned[item["ma_hp"]] = item
    needed = []
    source_rows = []
    if planned:
        for index, item in enumerate(plan["courses"]):
            known = by_code.get(item["ma_hp"], {})
            credits = item.get("tin_chi")
            if credits is None:
                credits = known.get("tin_chi") or 0
            name = item.get("ten_mon") or known.get("ten_mon") or item["ma_hp"]
            needed.append({
                "index": index,
                "ma_hp": item["ma_hp"],
                "ten_mon": name,
                "tin_chi": int(credits or 0),
                "norm": normalize(name),
                "code": str(item["ma_hp"]).strip().lower(),
                "hoc_ky": item.get("hoc_ky"),
                "loai": item.get("loai") or "bat_buoc",
                "nhom": item.get("nhom") or "",
            })
            source_rows.append(item)
    else:
        for index, row in enumerate(catalog):
            credits = int(row["tin_chi"] or 0)
            needed.append({
                "index": index,
                "ma_hp": row.get("ma_hp") or "",
                "ten_mon": row["ten_mon"],
                "tin_chi": credits,
                "norm": normalize(row["ten_mon"]),
                "code": str(row.get("ma_hp") or "").strip().lower(),
                "hoc_ky": None,
                "loai": "bat_buoc",
                "nhom": "",
            })

    passed = []
    studying = []
    for course in courses or []:
        if not isinstance(course, dict):
            continue
        if course_passed(course):
            passed.append(course)
        elif course_in_progress(course):
            studying.append(course)
    used_student = set()
    used_required = set()
    # Index pools separately so a Bảng 2 row does not collide with a Bảng 1 row.
    done_hits = _match_into(passed, needed, used_student, used_required, "dat", True)
    study_used_student = set()
    study_hits = _match_into(studying, needed, study_used_student, used_required, "dang_hoc", False)
    status = {req["index"]: "thieu" for req in needed}
    how = {}
    for _index, req, kind, score in done_hits:
        status[req["index"]] = "dat"
        how[req["index"]] = {"how": kind, "score": score}
    for _index, req, kind, score in study_hits:
        status[req["index"]] = "dang_hoc"
        how[req["index"]] = {"how": kind, "score": score}

    rows = []
    for req in needed:
        rows.append({
            "ma_hp": req["ma_hp"],
            "ten_mon": req["ten_mon"],
            "tin_chi": req["tin_chi"],
            "hoc_ky": req["hoc_ky"],
            "loai": req["loai"],
            "nhom": req["nhom"],
            "status": status[req["index"]],
            "how": (how.get(req["index"]) or {}).get("how"),
        })
    req_done, req_total, ele_done, ele_cap, percent = _completion(rows, plan if planned else None)
    done = [row for row in rows if row["status"] == "dat"]
    missing = [row for row in rows if row["status"] == "thieu"]
    semesters = []
    if planned:
        numbers = sorted({row["hoc_ky"] for row in rows if row["hoc_ky"]})
        totals = (plan or {}).get("tin_chi_ky") or {}
        for number in numbers:
            group = [row for row in rows if row["hoc_ky"] == number]
            semesters.append({
                "hoc_ky": number,
                "tin_chi_ky": totals.get(str(number)) or totals.get(number),
                "tin_chi": sum(row["tin_chi"] for row in group),
                "tin_chi_dat": sum(row["tin_chi"] for row in group if row["status"] == "dat"),
                "bat_buoc": [row for row in group if row["loai"] != "tu_chon"],
                "tu_chon": [row for row in group if row["loai"] == "tu_chon"],
            })
    note = "Môn đạt khi điểm chữ từ D trở lên hoặc điểm P."
    if not planned:
        note = "CTĐT chưa có thông tin phân kỳ. " + note
    elif plan.get("partial"):
        note = "Bản scan chỉ đọc được một phần các học kỳ. Những học kỳ dưới đây là phần đọc được, không phải danh sách tự điền. " + note
    elif plan.get("exclude_pe_qp"):
        note += " Giáo dục thể chất và giáo dục quốc phòng không cộng vào mốc tín chỉ tối thiểu, đúng lời ghi trên file CTĐT."
    if ele_cap is not None:
        note += f" Tự chọn tính tối đa {ele_cap} tín chỉ (mức tối thiểu in trong CTĐT), không tính mọi học phần tự chọn được liệt kê."
    return {
        "found": True,
        "nganh": nganh,
        "khoa": _khoa(nganh),
        "has_plan": bool(planned),
        "nguon": (plan or {}).get("nguon"),
        "tin_chi_toi_thieu": (plan or {}).get("tin_chi_toi_thieu"),
        "tu_chon_toi_thieu": ele_cap,
        "required_count": sum(1 for row in rows if row["loai"] != "tu_chon"),
        "required_credits": req_total,
        "required_done_credits": req_done,
        "elective_done_credits": ele_done,
        "done_count": len(done),
        "done_credits": req_done + (ele_done or 0),
        "remaining_credits": max(0, (req_total + (ele_cap or 0)) - (req_done + (ele_done or 0))),
        "missing_count": len(missing),
        "percent": percent,
        "done": done,
        "missing": missing,
        "semesters": semesters,
        "extra": [
            course.get("ten_mon") or ""
            for course in passed
            if (course.get("ten_mon") or "") not in {row["ten_mon"] for row in done}
        ],
        "note": note,
    }


def _khoa(nganh: str) -> str:
    for program in list_programs():
        if program["nganh"] == nganh:
            return program["khoa"] or ""
    return ""
