# -*- coding: utf-8 -*-
"""Học lại, học bổng khuyến khích, cảnh báo học vụ.

Ngưỡng cảnh báo lấy đúng quy tắc đã dùng trong regulations.py
(QĐ 1586 Điều 10, Thông tư 08/2021 Điều 11): GPA học kỳ đầu khóa dưới 0,8,
các học kỳ chính sau dưới 1,0, CPA tích lũy dưới 1,2 / 1,4 / 1,6 / 1,8 theo năm,
và tín chỉ không đạt vượt 50% tín chỉ đăng ký trong kỳ.

Học bổng khuyến khích học tập theo Nghị định 84/2020/NĐ-CP Điều 8
(kết quả học tập và rèn luyện từ Khá trở lên) và thang điểm rèn luyện
Thông tư 16/2015/TT-BGDĐT Điều 9, thang GPA QĐ 1586. Cổng «không có học phần
không đạt» là điều các thông báo học bổng của trường thành viên ĐHĐN đang ghi
(ví dụ thông báo VKU các học kỳ 2021–2023). Mức tín chỉ tối thiểu nằm trong
hằng số để sửa khi nhà trường đổi phụ lục tiến độ.
"""
from __future__ import annotations

import math
from decimal import Decimal

import regulations

# Theo quy định hiện hành, có thể thay đổi.
SCHOLARSHIP = {
    "min_credits": 15,
    "cite": "Nghị định 84/2020/NĐ-CP Điều 8; điểm rèn luyện Thông tư 16/2015 Điều 9; GPA theo QĐ 1586.",
    "tiers": (
        {"name": "Xuất sắc", "gpa": Decimal("3.60"), "drl": 90, "drl_label": "Xuất sắc"},
        {"name": "Giỏi", "gpa": Decimal("3.20"), "drl": 80, "drl_label": "Tốt"},
        {"name": "Khá", "gpa": Decimal("2.50"), "drl": 65, "drl_label": "Khá"},
    ),
}

RETAKE_TARGETS = {"A+": Decimal("4.0"), "A": Decimal("4.0"), "B+": Decimal("3.5"), "B": Decimal("3.0")}

WARN_CITE = (
    "QĐ 1586/QĐ-ĐHSP Điều 10 và Thông tư 08/2021 Điều 11: "
    "GPA học kỳ đầu khóa dưới 0,8, các học kỳ chính sau dưới 1,0, "
    "CPA dưới 1,2 / 1,4 / 1,6 / 1,8 theo năm học, "
    "tín chỉ không đạt vượt 50% tín chỉ đăng ký trong kỳ."
)


def _cpa(courses) -> tuple[float | None, float]:
    out = regulations.summarize({"courses": courses, "rule": "qd1586", "program_credits": 130})
    cumulative = out["cumulative"]
    return cumulative["gpa"], float(cumulative["credits_in_gpa"] or 0)


def _groups(courses):
    grouped = {}
    for course in courses or []:
        if not isinstance(course, dict):
            continue
        name = " ".join(str(course.get("ten_mon") or "").split())
        if not name or course.get("pass_only"):
            continue
        letter = str(course.get("diem_he_4") or "").upper().replace(" ", "")
        if course.get("diem_10") in (None, "") and letter in ("", "P", "I", "X", "R"):
            continue
        grouped.setdefault(name, []).append(course)
    return grouped


def _credits(group) -> float:
    for course in reversed(group):
        try:
            return float(course.get("tin_chi") or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _with_retakes(courses, picks):
    """picks: list of (name, credits, letter). A later attempt keeps the highest pass, or replaces F."""
    cloned = [dict(course) for course in courses]
    lan = {}
    for course in cloned:
        name = " ".join(str(course.get("ten_mon") or "").split())
        try:
            seen = int(course.get("lan") or 1)
        except (TypeError, ValueError):
            seen = 1
        lan[name] = max(lan.get(name, 1), seen)
    for name, credits, letter in picks:
        lan[name] = lan.get(name, 1) + 1
        cloned.append({
            "ten_mon": name,
            "tin_chi": credits,
            "diem_he_4": letter,
            "nam_hoc": "2099-2100",
            "hoc_ky": "2",
            "lan": lan[name],
        })
    return cloned


def retake_suggestions(courses, target="A", top_n=5) -> dict:
    letter = str(target or "A").upper().replace(" ", "")
    if letter not in RETAKE_TARGETS:
        raise ValueError("Chọn điểm mục tiêu A+, A, B+ hoặc B")
    courses = list(courses or [])
    now, _credits_now = _cpa(courses)
    ranked = []
    for name, group in _groups(courses).items():
        credits = _credits(group)
        if credits <= 0:
            continue
        after, _ = _cpa(_with_retakes(courses, [(name, credits, letter)]))
        gain = None if now is None or after is None else round(after - now, 4)
        if not gain or gain <= 0:
            continue
        latest = group[-1]
        ranked.append({
            "ten_mon": name,
            "tin_chi": credits,
            "from_letter": latest.get("diem_he_4") or "",
            "cpa_after": after,
            "gain": round(gain, 2),
        })
    ranked.sort(key=lambda item: (-item["gain"], -item["tin_chi"], item["ten_mon"]))
    singles = ranked[:top_n]
    pairs = []
    pool = ranked[: max(top_n, 6)]
    for i, left in enumerate(pool):
        for right in pool[i + 1:]:
            after, _ = _cpa(_with_retakes(courses, [
                (left["ten_mon"], left["tin_chi"], letter),
                (right["ten_mon"], right["tin_chi"], letter),
            ]))
            gain = None if now is None or after is None else round(after - now, 2)
            if not gain or gain <= 0:
                continue
            pairs.append({
                "courses": [left["ten_mon"], right["ten_mon"]],
                "cpa_after": after,
                "gain": gain,
            })
    pairs.sort(key=lambda item: (-item["gain"], item["courses"]))
    return {
        "target": letter,
        "target_points": float(RETAKE_TARGETS[letter]),
        "cpa_now": now,
        "singles": singles,
        "pairs": pairs[:3],
        "rule": "QĐ 1586: học phần đã đạt giữ điểm cao nhất khi học cải thiện; học phần chưa đạt lấy lần học cuối. Điểm F đang nợ không nằm trong mẫu số CPA.",
    }


def _tier_for(gpa, drl):
    if gpa is None:
        return None
    g = Decimal(str(gpa))
    for tier in SCHOLARSHIP["tiers"]:
        if g >= tier["gpa"] and drl is not None and drl >= tier["drl"]:
            return tier["name"]
    return None


def scholarship_report(courses, drl=None, discipline=False, program_credits=130) -> dict:
    out = regulations.summarize({
        "courses": courses or [],
        "rule": "qd1586",
        "program_credits": program_credits,
    })
    try:
        conduct = None if drl in (None, "") else int(drl)
    except (TypeError, ValueError):
        conduct = None
    semesters = []
    for sem in out["semesters"]:
        if sem.get("hoc_ky") not in ("1", "2"):
            continue
        gpa = sem.get("gpa")
        registered = float(sem.get("registered") or sem.get("credits") or 0)
        failed = float(sem.get("failed_credits") or 0)
        reasons = []
        if discipline:
            reasons.append("Bị kỷ luật từ khiển trách trở lên trong học kỳ xét thì không xét học bổng.")
        if registered < SCHOLARSHIP["min_credits"]:
            reasons.append(f"Chưa đủ {SCHOLARSHIP['min_credits']} tín chỉ đăng ký trong học kỳ (đang {registered:g}).")
        if failed > 0:
            reasons.append("Có học phần không đạt trong học kỳ xét.")
        if conduct is None:
            reasons.append("Chưa nhập điểm rèn luyện của học kỳ.")
        tier = None if reasons else _tier_for(gpa, conduct)
        if not reasons and tier is None:
            reasons.append("GPA học kỳ hoặc điểm rèn luyện chưa đạt mức Khá.")
        semesters.append({
            "nam_hoc": sem.get("nam_hoc"),
            "hoc_ky": sem.get("hoc_ky"),
            "gpa": gpa,
            "registered": registered,
            "failed_credits": failed,
            "tier": tier,
            "eligible": tier is not None,
            "reasons": reasons,
        })
    return {
        "cite": SCHOLARSHIP["cite"],
        "label": "theo quy định hiện hành, có thể thay đổi",
        "min_credits": SCHOLARSHIP["min_credits"],
        "drl": conduct,
        "tiers": [
            {"name": tier["name"], "gpa": float(tier["gpa"]), "drl": tier["drl"], "drl_label": tier["drl_label"]}
            for tier in SCHOLARSHIP["tiers"]
        ],
        "semesters": semesters,
    }


def _credits_at_four(gpa, credits, target: Decimal):
    if gpa is None or not credits or Decimal(str(gpa)) >= target:
        return 0
    gap = target * Decimal(str(credits)) - Decimal(str(gpa)) * Decimal(str(credits))
    per = Decimal("4") - target
    if per <= 0:
        return None
    return int(math.ceil(gap / per))


def warning_report(courses, program_credits=130, rule="qd1586") -> dict:
    out = regulations.summarize({
        "courses": courses or [],
        "rule": rule or "qd1586",
        "program_credits": program_credits,
    })
    semesters = []
    for sem in out["semesters"]:
        semesters.append({
            "nam_hoc": sem.get("nam_hoc"),
            "hoc_ky": sem.get("hoc_ky"),
            "gpa": sem.get("gpa"),
            "cumulative_gpa": sem.get("cumulative_gpa"),
            "registered": sem.get("registered"),
            "failed_credits": sem.get("failed_credits"),
            "year_standing": sem.get("year_standing"),
            "warning": bool(sem.get("warning")),
            "warning_reasons": sem.get("warning_reasons") or [],
        })
    warned = [sem for sem in semesters if sem["warning"]]
    count = int(out.get("warnings_count") or 0)
    if count >= 2:
        level, label = "lien_tiep", "Đã có từ 2 học kỳ cảnh báo"
    elif warned:
        level, label = "canh_bao", "Đang thuộc diện cảnh báo học tập"
    else:
        level, label = "khong", "Chưa thấy mức cảnh báo trên các học kỳ đã nhập"
    cumulative = out["cumulative"]
    standing = semesters[-1]["year_standing"] if semesters else 1
    cap = regulations.CUM_WARN.get(standing or 1, Decimal("1.8"))
    needed = _credits_at_four(cumulative.get("gpa"), cumulative.get("credits_in_gpa") or 0, cap)
    steps = []
    if needed:
        steps.append(f"Để CPA đạt ngưỡng năm thứ {standing} ({cap}), cần thêm khoảng {needed} tín chỉ điểm 4,0, nếu các môn hiện tại không đổi.")
    elif cumulative.get("gpa") is not None and Decimal(str(cumulative["gpa"])) < cap:
        steps.append(f"CPA đang dưới {cap}. Với điểm tối đa 4,0 vẫn chưa kéo được lên ngưỡng này bằng các môn mới.")
    else:
        steps.append(f"CPA đang không dưới ngưỡng năm thứ {standing} ({cap}).")
    steps.append("Học kỳ chính tiếp theo cần GPA từ 1,0 trở lên (0,8 nếu đó là học kỳ đầu khóa) và tín chỉ không đạt không quá 50% tín chỉ đăng ký.")
    if out.get("dismissal_note"):
        steps.append(out["dismissal_note"])
    return {
        "level": level,
        "label": label,
        "warnings_count": count,
        "semesters": semesters,
        "cumulative_gpa": cumulative.get("gpa"),
        "year_standing": standing,
        "cumulative_cap": float(cap),
        "exit_steps": steps,
        "cite": WARN_CITE,
    }
