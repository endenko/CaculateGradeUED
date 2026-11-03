# -*- coding: utf-8 -*-
"""Giải mục tiêu CPA / GPA học kỳ cho bảng điểm 2 bảng.

Chạy phía client (bản JS cùng công thức). File này là nguồn kiểm thử.
Thang chữ: Quyết định 1586 Điều 8. A và A+ cùng 4,0 nên khi phân bổ
điểm để đạt mục tiêu, máy chọn A (ngưỡng 8,5) chứ không buộc A+ (9,5).
"""
from __future__ import annotations

from decimal import Decimal

from regulations import letter_from_score10, round1, round2

# Điểm hệ 4 tăng dần. Cùng 4,0 thì lấy ngưỡng hệ 10 thấp hơn (A, không A+).
PLAN_LETTERS = (
    ("D", Decimal("4.0"), Decimal("1.0")),
    ("D+", Decimal("5.0"), Decimal("1.5")),
    ("C", Decimal("5.5"), Decimal("2.0")),
    ("C+", Decimal("6.5"), Decimal("2.5")),
    ("B", Decimal("7.0"), Decimal("3.0")),
    ("B+", Decimal("8.0"), Decimal("3.5")),
    ("A", Decimal("8.5"), Decimal("4.0")),
)
LOW_GRADES = {"C", "D+", "D", "F"}


def _d(value) -> Decimal:
    return Decimal(str(value))


def letter_of(score10) -> tuple[str, float]:
    letter, pts = letter_from_score10(score10, "qd1586")
    return letter, float(pts)


def component_score(bp, gk, ck, weights=(0.2, 0.3, 0.5)) -> dict:
    wbp, wgk, wck = (_d(weights[0]), _d(weights[1]), _d(weights[2]))
    if abs((wbp + wgk + wck) - 1) > Decimal("0.001"):
        raise ValueError("Tổng trọng số phải bằng 1")
    raw = _d(bp) * wbp + _d(gk) * wgk + _d(ck) * wck
    rounded = round1(raw)
    letter, pts = letter_from_score10(rounded, "qd1586")
    return {"raw": float(raw), "score10": float(rounded), "letter": letter, "points": float(pts)}


def min_ck(bp, gk, min_score10, weights=(0.2, 0.3, 0.5)):
    """Điểm CK nhỏ nhất (bước 0,1) sao cho điểm học phần làm tròn đạt ngưỡng chữ."""
    wbp, wgk, wck = (_d(weights[0]), _d(weights[1]), _d(weights[2]))
    if wck <= 0:
        return None
    target = _d(min_score10)
    step = Decimal("0.1")
    ck = Decimal("0")
    while ck <= Decimal("10") + step / 2:
        rounded = round1(_d(bp) * wbp + _d(gk) * wgk + ck * wck)
        if rounded >= target:
            return float(ck)
        ck += step
    return None


def cpa(rows) -> dict:
    """rows: {credits, points}. Điểm làm tròn 2 chữ số."""
    credits = Decimal("0")
    quality = Decimal("0")
    for row in rows:
        tc = _d(row["credits"])
        credits += tc
        quality += _d(row["points"]) * tc
    if credits == 0:
        return {"cpa": None, "credits": 0.0, "quality": 0.0}
    return {"cpa": float(round2(quality / credits)), "credits": float(credits), "quality": float(quality)}


def _ck_for(course, min_score, weights):
    return min_ck(course["bp"], course["gk"], min_score, weights)


def _best_under_cap(course, cap, weights):
    chosen = None
    for letter, minimum, points in PLAN_LETTERS:
        ck = _ck_for(course, minimum, weights)
        if ck is None or ck > cap + 1e-9:
            continue
        chosen = {"letter": letter, "min_score10": float(minimum), "points": float(points), "ck": ck}
    return chosen


def _gpa_value(fixed, variable, assignment):
    rows = [{"credits": r["credits"], "points": r["points"]} for r in fixed]
    for course in variable:
        plan = assignment[course["id"]]
        rows.append({"credits": course["credits"], "points": plan["points"]})
    return cpa(rows)


def _downgrade(fixed, variable, assignment, target):
    """Hạ chữ từng môn (ưu tiên môn đang đòi CK cao) nếu CPA vẫn đạt mục tiêu."""
    guard = 0
    while guard < 500:
        guard += 1
        order = sorted(variable, key=lambda c: assignment[c["id"]]["ck"], reverse=True)
        changed = False
        for course in order:
            current = assignment[course["id"]]
            idx = next(i for i, item in enumerate(PLAN_LETTERS) if item[0] == current["letter"])
            if idx == 0:
                continue
            letter, minimum, points = PLAN_LETTERS[idx - 1]
            ck = _ck_for(course, minimum, course["weights"])
            trial = dict(assignment)
            trial[course["id"]] = {"letter": letter, "min_score10": float(minimum), "points": float(points), "ck": ck}
            stats = _gpa_value(fixed, variable, trial)
            if stats["cpa"] is not None and stats["cpa"] + 1e-9 >= target:
                assignment = trial
                changed = True
                break
        if not changed:
            break
    return assignment


def _label(max_ck, impossible: bool) -> str:
    if impossible or max_ck is None or max_ck > 10:
        return "Bất khả thi trong kỳ này"
    if max_ck >= 8.5:
        return "Khó (cần CK >= 8.5)"
    return "Khả thi (Dễ/Trung bình)"


def _retake_suggestions(table1, base_rows, variable, weights, target):
    """Xếp môn bảng 1 theo mức tăng điểm hệ 4 trên mỗi tín chỉ nếu học lại thành A."""
    ranked = []
    for course in table1:
        points = _d(course["points"])
        gain_per_credit = float(Decimal("4") - points)
        if gain_per_credit <= 0:
            continue
        ranked.append((gain_per_credit, _d(course["credits"]), course))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    # Ưu tiên môn tô đỏ (>= 3 TC và C/D+/D/F) nhưng vẫn liệt kê môn khác nếu cần.
    highlighted = [item for item in ranked if item[2].get("highlight")]
    ordered = highlighted + [item for item in ranked if item not in highlighted]
    suggestions = []
    lifted = []
    for _gain, _tc, course in ordered[:8]:
        lifted.append(course)
        fixed = [row for row in base_rows if row.get("id") != course["id"]]
        fixed.append({"id": course["id"], "credits": course["credits"], "points": 4.0})
        solved = _assign(fixed, variable, weights, target)
        projected_rows = fixed + [
            {"credits": c["credits"], "points": solved["assignment"][c["id"]]["points"]}
            for c in variable
            if solved["assignment"].get(c["id"])
        ]
        suggestions.append({
            "id": course["id"],
            "ten_mon": course.get("ten_mon"),
            "credits": course["credits"],
            "from_letter": course.get("letter"),
            "to_letter": "A",
            "gain_per_credit": round(_gain, 2),
            "projected_cpa": cpa(projected_rows)["cpa"],
            "feasible_after": solved["label"] != "Bất khả thi trong kỳ này",
        })
        if solved["label"] != "Bất khả thi trong kỳ này":
            break
    return suggestions


def _assign(fixed, variable, weights, target):
    if not variable:
        stats = cpa(fixed)
        reached = stats["cpa"] is not None and stats["cpa"] + 1e-9 >= target
        return {
            "assignment": {},
            "cpa": stats["cpa"],
            "credits": stats["credits"],
            "max_ck": None,
            "label": "Khả thi (Dễ/Trung bình)" if reached else "Bất khả thi trong kỳ này",
            "courses": [],
        }
    feasible = None
    cap = Decimal("0")
    while cap <= Decimal("10") + Decimal("0.05"):
        assignment = {}
        ok = True
        for course in variable:
            course = {**course, "weights": weights}
            plan = _best_under_cap(course, float(cap), weights)
            if plan is None:
                ok = False
                break
            assignment[course["id"]] = plan
        if ok:
            stats = _gpa_value(fixed, variable, assignment)
            if stats["cpa"] is not None and stats["cpa"] + 1e-9 >= target:
                feasible = (float(cap), assignment, stats)
                break
        cap += Decimal("0.1")
    impossible = feasible is None
    if impossible:
        assignment = {}
        for course in variable:
            ck = _ck_for({**course, "weights": weights}, Decimal("8.5"), weights)
            assignment[course["id"]] = {
                "letter": "A",
                "min_score10": 8.5,
                "points": 4.0,
                "ck": ck if ck is not None else 10.1,
            }
        stats = _gpa_value(fixed, variable, assignment)
        max_ck = max(item["ck"] for item in assignment.values())
    else:
        _cap, assignment, stats = feasible
        variable_w = [{**c, "weights": weights} for c in variable]
        assignment = _downgrade(fixed, variable_w, assignment, target)
        stats = _gpa_value(fixed, variable, assignment)
        max_ck = max(item["ck"] for item in assignment.values())
        if max_ck > 10:
            impossible = True
    courses_out = []
    for course in variable:
        plan = assignment[course["id"]]
        courses_out.append({
            "id": course["id"],
            "ten_mon": course.get("ten_mon"),
            "credits": course["credits"],
            "letter": plan["letter"],
            "points": plan["points"],
            "min_score10": plan["min_score10"],
            "min_ck": None if plan["ck"] is None or plan["ck"] > 10 else plan["ck"],
            "ck_over": plan["ck"] is None or plan["ck"] > 10,
        })
    return {
        "assignment": assignment,
        "cpa": stats["cpa"],
        "credits": stats["credits"],
        "max_ck": max_ck,
        "label": _label(max_ck, impossible),
        "courses": courses_out,
    }


def _pack(course, use_sim=False):
    points = course["points"]
    letter = course.get("letter")
    if use_sim and course.get("sim") and course.get("sim_points") is not None:
        points = course["sim_points"]
        letter = course.get("sim_letter")
    return {
        "id": course["id"],
        "ten_mon": course.get("ten_mon"),
        "credits": course["credits"],
        "points": points,
        "letter": letter,
        "highlight": (course.get("credits") or 0) >= 3 and letter in LOW_GRADES,
    }


def _split_semester(table2, weights):
    fixed, variable = [], []
    for course in table2:
        bp, gk, ck = course.get("bp"), course.get("gk"), course.get("ck")
        if bp is not None and gk is not None and ck is None:
            variable.append({
                "id": course["id"], "ten_mon": course.get("ten_mon"),
                "credits": course["credits"], "bp": bp, "gk": gk, "weights": weights,
            })
        elif course.get("points") is not None:
            fixed.append(_pack(course))
    return fixed, variable


def _plan_from_choice(fixed, variable, choice):
    """choice: list of (letter, minimum, points, ck) aligned with variable."""
    rows = [{"credits": r["credits"], "points": r["points"]} for r in fixed]
    courses = []
    max_ck = 0.0
    sum_ck = 0.0
    any_over = False
    for course, (letter, minimum, points, ck) in zip(variable, choice):
        over = ck is None or ck > 10
        if over:
            any_over = True
            shown = None
        else:
            max_ck = max(max_ck, ck)
            sum_ck += ck
            shown = ck
        rows.append({"credits": course["credits"], "points": points})
        courses.append({
            "id": course["id"],
            "ten_mon": course.get("ten_mon"),
            "credits": course["credits"],
            "letter": letter,
            "min_ck": shown,
            "ck_over": over,
        })
    stats = cpa(rows)
    return {
        "gpa": stats["cpa"],
        "max_ck": None if any_over else max_ck,
        "sum_ck": None if any_over else round(sum_ck, 1),
        "feasible": (not any_over) and stats["cpa"] is not None,
        "courses": courses,
        "summary": ", ".join(f"{c['ten_mon']} {c['letter']}" for c in courses),
    }


def semester_options(table2, target, weights=(0.2, 0.3, 0.5), limit=5) -> list:
    """Tối đa `limit` phương án chữ cho môn đang học, dễ nhất (CK thấp) trước."""
    target = float(target)
    weights = tuple(float(w) for w in weights)
    if abs(sum(weights) - 1) > 0.001:
        raise ValueError("Tổng trọng số phải bằng 1")
    limit = max(1, min(int(limit), 5))
    fixed, variable = _split_semester(table2, weights)
    if not variable:
        stats = cpa(fixed)
        if not fixed and not table2:
            return [{"kind": "empty", "courses": [], "summary": "", "feasible": False, "gpa": None}]
        return [{
            "kind": "idle",
            "gpa": stats["cpa"],
            "max_ck": None,
            "sum_ck": None,
            "feasible": stats["cpa"] is not None and stats["cpa"] + 1e-9 >= target,
            "courses": [],
            "summary": "Không có môn đang chờ điểm cuối kỳ",
            "label": "Không có môn đang chờ điểm cuối kỳ",
        }]

    prepared = []
    for course in variable:
        opts = []
        for letter, minimum, points in PLAN_LETTERS:
            ck = _ck_for(course, minimum, weights)
            opts.append((letter, float(minimum), float(points), ck))
        prepared.append(opts)

    found = []

    def walk(i, acc):
        if len(found) > 2500:
            return
        if i == len(prepared):
            plan = _plan_from_choice(fixed, variable, acc)
            if plan["feasible"] and plan["gpa"] + 1e-9 >= target:
                found.append(plan)
            return
        for opt in prepared[i]:
            acc.append(opt)
            walk(i + 1, acc)
            acc.pop()

    if len(variable) <= 4:
        walk(0, [])
    else:
        # Quá nhiều tổ hợp: lấy phương án gốc rồi đổi từng môn một bậc.
        base = _assign(fixed, variable, weights, target)
        seeds = [base["courses"]]
        letters = [item[0] for item in PLAN_LETTERS]
        for seed in list(seeds):
            for idx, course in enumerate(variable):
                cur = next(c for c in seed if c["id"] == course["id"])
                pos = letters.index(cur["letter"]) if cur["letter"] in letters else len(letters) - 1
                for delta in (-1, 1):
                    npos = pos + delta
                    if npos < 0 or npos >= len(letters):
                        continue
                    trial = []
                    for course2, opt_list in zip(variable, prepared):
                        if course2["id"] == course["id"]:
                            picked = next(o for o in opt_list if o[0] == letters[npos])
                        else:
                            want = next(c["letter"] for c in seed if c["id"] == course2["id"])
                            picked = next(o for o in opt_list if o[0] == want)
                        trial.append(picked)
                    plan = _plan_from_choice(fixed, variable, trial)
                    if plan["feasible"] and plan["gpa"] + 1e-9 >= target:
                        found.append(plan)
        plan0_choice = []
        for course, opt_list in zip(variable, prepared):
            want = next(c for c in base["courses"] if c["id"] == course["id"])
            plan0_choice.append(next(o for o in opt_list if o[0] == want["letter"]))
        plan0 = _plan_from_choice(fixed, variable, plan0_choice)
        if plan0["feasible"] and plan0["gpa"] + 1e-9 >= target:
            found.append(plan0)

    ranked = sorted(found, key=lambda p: (p["max_ck"], p["sum_ck"], -p["gpa"]))
    out = []
    seen = set()
    for plan in ranked:
        key = tuple((c["id"], c["letter"]) for c in plan["courses"])
        if key in seen:
            continue
        seen.add(key)
        plan["label"] = _label(plan["max_ck"], False)
        out.append(plan)
        if len(out) >= limit:
            break
    if out:
        return out
    # Không cách nào đạt: một phương án tất cả A để thấy CK vượt 10.
    forced = []
    for course, opt_list in zip(variable, prepared):
        forced.append(opt_list[-1])
    plan = _plan_from_choice(fixed, variable, forced)
    plan["feasible"] = False
    plan["label"] = "Bất khả thi trong kỳ này"
    return [plan]


def solve(table1, table2, target, scope="overall", weights=(0.2, 0.3, 0.5)) -> dict:
    """scope 'overall': CPA bảng 1 (kể cả giả lập) + bảng 2. 'semester': chỉ bảng 2.

    Môn bảng 2 có BP và GK nhưng CK trống được phân bổ. Môn đã có điểm chữ
    hoặc đã nhập đủ CK tính là điểm cố định.
    """
    target = float(target)
    weights = tuple(float(w) for w in weights)
    if abs(sum(weights) - 1) > 0.001:
        raise ValueError("Tổng trọng số phải bằng 1")

    fixed = []
    variable = []
    if scope == "overall":
        fixed.extend(_pack(c, use_sim=True) for c in table1)
    for course in table2:
        bp, gk, ck = course.get("bp"), course.get("gk"), course.get("ck")
        if bp is not None and gk is not None and ck is None:
            variable.append({
                "id": course["id"], "ten_mon": course.get("ten_mon"),
                "credits": course["credits"], "bp": bp, "gk": gk,
            })
        elif course.get("points") is not None:
            fixed.append(_pack(course))
    result = _assign(fixed, variable, weights, target)
    current_rows = list(fixed)
    if scope == "overall":
        current_rows = [_pack(c, use_sim=True) for c in table1]
        current_rows += [_pack(c) for c in table2 if c.get("points") is not None and not (
            c.get("bp") is not None and c.get("gk") is not None and c.get("ck") is None
        )]
    suggestions = []
    if result["label"] == "Bất khả thi trong kỳ này" and scope == "overall":
        suggestions = _retake_suggestions(
            [_pack(c, use_sim=True) for c in table1], fixed, variable, weights, target)
    result.update({
        "target": target,
        "scope": scope,
        "current_cpa": cpa(current_rows)["cpa"],
        "current_credits": cpa([_pack(c, use_sim=True) for c in table1])["credits"] if scope == "overall" else cpa(fixed)["credits"],
        "weights": list(weights),
        "retakes": suggestions,
    })
    return result
