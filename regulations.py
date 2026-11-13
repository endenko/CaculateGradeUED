# -*- coding: utf-8 -*-
"""Quy đổi điểm và xếp loại theo văn bản đã đối chiếu.

Nguồn (không suy diễn thêm ngưỡng):
- Thông tư 08/2021/TT-BGDĐT, Điều 9, 10, 11, 14 — áp dụng từ khóa 2021
  theo trang Phòng Đào tạo UED (https://daotao.ued.udn.vn/quy-dinh-ve-dao-tao/).
- Quyết định 1473/QĐ-ĐHSP-ĐT (15/10/2019), Điều 15, 16, 19, 20, 21, 25 —
  khóa 2020 trở về trước
  (https://daotao.ued.udn.vn/quyet-dinh-442-qd-dhsp-dt-ve-viec-ban-hanh-quy-dinh-dao-tao-trinh-do-dai-hoc-va-cao-dang-he-chinh-quy-theo-he-thong-tin-chi/).
- Thông tư 16/2015/TT-BGDĐT, Điều 4–10 — điểm rèn luyện.

Quyết định 1498/QĐ-ĐHSP ngày 31/7/2025 được Phòng Đào tạo liệt kê
(áp dụng từ khóa 2025) nhưng toàn văn chưa lấy được trong bản này.
Những chỗ 1498 có thể sửa thì ghi unverified, không bịa số.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# QĐ 1586/QĐ-ĐHSP (30/9/2021) Điều 8.4 — khóa 2021 trở đi. A+ và A cùng 4,0.
BANDS_1586 = (
    ("A+", Decimal("9.5"), Decimal("4.0")),
    ("A", Decimal("8.5"), Decimal("4.0")),
    ("B+", Decimal("8.0"), Decimal("3.5")),
    ("B", Decimal("7.0"), Decimal("3.0")),
    ("C+", Decimal("6.5"), Decimal("2.5")),
    ("C", Decimal("5.5"), Decimal("2.0")),
    ("D+", Decimal("5.0"), Decimal("1.5")),
    ("D", Decimal("4.0"), Decimal("1.0")),
    ("F", Decimal("0"), Decimal("0")),
)
# QĐ 1473 Điều 20 — khóa 2020 trở về trước, không có bậc cộng.
BANDS_1473 = (
    ("A", Decimal("8.5"), Decimal("4")),
    ("B", Decimal("7.0"), Decimal("3")),
    ("C", Decimal("5.5"), Decimal("2")),
    ("D", Decimal("4.0"), Decimal("1")),
    ("F", Decimal("0"), Decimal("0")),
)
_BANDS = BANDS_1586  # mặc định hiện hành
LETTER_POINTS = {name: pts for name, _lo, pts in BANDS_1586}

# TT 08 Điều 10.5.a / QĐ 1473 Điều 25 (hạng tốt nghiệp chỉ tới Trung bình).
HOC_LUC = (
    ("Xuất sắc", Decimal("3.60"), Decimal("4.00")),
    ("Giỏi", Decimal("3.20"), Decimal("3.59")),
    ("Khá", Decimal("2.50"), Decimal("3.19")),
    ("Trung bình", Decimal("2.00"), Decimal("2.49")),
    ("Yếu", Decimal("1.00"), Decimal("1.99")),
    ("Kém", Decimal("0"), Decimal("0.99")),
)
# TT 08 Điều 11.1.c — ngưỡng điểm TB tích lũy theo trình độ năm.
CUM_WARN = {1: Decimal("1.2"), 2: Decimal("1.4"), 3: Decimal("1.6"), 4: Decimal("1.8"), 5: Decimal("1.8")}

DRL_CAPS = (
    ("hoc_tap", "Ý thức tham gia học tập", 20, "Điều 4"),
    ("noi_quy", "Ý thức chấp hành nội quy, quy chế, quy định trong nhà trường", 25, "Điều 5"),
    ("hoat_dong", "Ý thức tham gia hoạt động chính trị, xã hội, văn hóa, văn nghệ, thể thao, phòng chống tội phạm và tệ nạn xã hội", 20, "Điều 6"),
    ("cong_dan", "Ý thức công dân trong quan hệ cộng đồng", 25, "Điều 7"),
    ("can_bo", "Ý thức và kết quả tham gia công tác cán bộ lớp, đoàn thể, hoặc thành tích đặc biệt", 10, "Điều 8"),
)

# QĐ 1586 Điều 8.1.b — quá trình 0,2 và giữa kỳ 0,3 (hoặc ngược lại), thi kết thúc 0,5.
PRESET_1586 = [
    {"name": "Đánh giá quá trình", "weight": 0.2, "exam": False},
    {"name": "Kiểm tra giữa kỳ", "weight": 0.3, "exam": False},
    {"name": "Thi kết thúc học phần", "weight": 0.5, "exam": True},
]
# QĐ 1473 Điều 19.1.a — học phần lý thuyết / lý thuyết+thực hành. Bộ phận 1 và 2 có thể đổi theo học phần.
PRESET_1473 = [
    {"name": "Bộ phận 1 (bài tập, chuyên cần, tiểu luận, thực hành…)", "weight": 0.1, "exam": False},
    {"name": "Bộ phận 2 (tiểu luận, thực hành…)", "weight": 0.1, "exam": False},
    {"name": "Kiểm tra giữa kỳ", "weight": 0.3, "exam": False},
    {"name": "Thi kết thúc học phần", "weight": 0.5, "exam": True},
]

_KY_ORDER = {"1": 1, "2": 2, "he": 3}


def _d(value) -> Decimal:
    return Decimal(str(value))


def round1(value) -> Decimal:
    """Làm tròn 1 chữ số thập phân, half up — Điều 9.3 TT 08 / Điều 20 QĐ 1473."""
    return _d(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def round2(value) -> Decimal:
    return _d(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_rule(rule: str) -> str:
    if rule in ("tt08", "qd1586", "qd2025"):
        return rule if rule != "tt08" else "qd1586"
    if rule == "qd1473":
        return rule
    raise ValueError("rule phải là qd1586, qd2025 hoặc qd1473")


def _bands(rule: str):
    return BANDS_1473 if _normalize_rule(rule) == "qd1473" else BANDS_1586


def letter_from_score10(score, rule: str = "qd1586") -> tuple[str, Decimal]:
    s = round1(score)
    if s < 0 or s > Decimal("10"):
        raise ValueError("Điểm hệ 10 phải trong khoảng 0–10")
    for name, lo, pts in _bands(rule):
        if s >= lo:
            return name, pts
    return "F", Decimal("0")


def hoc_luc(gpa) -> str | None:
    if gpa is None:
        return None
    g = _d(gpa)
    for name, lo, hi in HOC_LUC:
        if lo <= g <= hi:
            return name
    return None


def hang_tot_nghiep(gpa) -> str | None:
    """Điều 14.3 TT 08 và Điều 25 QĐ 1473 — chỉ 4 hạng, GPA từ 2,00."""
    name = hoc_luc(gpa)
    if name in ("Xuất sắc", "Giỏi", "Khá", "Trung bình"):
        return name
    return None


def _downgrade(rank: str | None) -> str | None:
    order = ["Xuất sắc", "Giỏi", "Khá", "Trung bình"]
    if rank not in ("Xuất sắc", "Giỏi"):
        return rank
    return order[order.index(rank) + 1]


def _course_key(course: dict) -> str:
    return " ".join(str(course.get("ten_mon") or "").strip().lower().split())


def _term_key(course: dict):
    nam = str(course.get("nam_hoc") or "").strip()
    ky = str(course.get("hoc_ky") or "").strip().lower()
    try:
        year = int(nam.split("-")[0])
    except (ValueError, IndexError):
        year = 9999
    return (year, _KY_ORDER.get(ky, 9), nam, ky)


def _attempt_sort(course: dict, index: int):
    y, k, _nam, _ky = _term_key(course)
    try:
        lan = int(course.get("lan") or 1)
    except (TypeError, ValueError):
        lan = 1
    return (y, k, lan, index)


def _points(course: dict, rule: str = "qd1586", use_sim: bool = False):
    """Trả (letter, points, source) hoặc ('skip', reason)."""
    table = {name: pts for name, _lo, pts in _bands(rule)}
    if use_sim and course.get("sim_grade"):
        letter = str(course["sim_grade"]).upper().replace(" ", "")
        if letter in table:
            return letter, table[letter], "sim"
        return "skip", f"Điểm giả lập {letter} không thuộc thang của quy định đang chọn"
    if course.get("diem_10") is not None and course.get("diem_10") != "":
        try:
            letter, pts = letter_from_score10(course["diem_10"], rule)
        except ValueError as exc:
            return "skip", str(exc)
        return letter, pts, "diem_10"
    letter = str(course.get("diem_he_4") or "").upper().replace(" ", "")
    if letter in table:
        return letter, table[letter], "letter"
    if letter in ("P", "I", "X", "R"):
        return letter, None, "special"
    return "skip", "Thiếu điểm hệ 10 hoặc điểm chữ thuộc quy định đang chọn"


def _weighted(rows):
    credits = Decimal("0")
    points = Decimal("0")
    for credits_i, pts in rows:
        credits += credits_i
        points += pts * credits_i
    if credits == 0:
        return None, Decimal("0"), Decimal("0")
    return round2(points / credits), credits, points


def _year_standing(passed_credits: Decimal, rule: str, program_credits: Decimal, m_override) -> int:
    n = passed_credits
    if rule == "qd1473":
        # Điều 15 QĐ 1473.
        if n < 34:
            return 1
        if n <= 65:
            return 2
        if n <= 99:
            return 3
        return 4
    if rule == "qd2025":
        # QĐ 1498, chương trình thiết kế 10 học kỳ, khóa 2025 trở đi.
        if n < 39:
            return 1
        if n < 78:
            return 2
        if n < 117:
            return 3
        return 4
    # QĐ 1586 Điều 9: N < 33, 33–65, 66–98, từ 99.
    if n < 33:
        return 1
    if n < 66:
        return 2
    if n < 99:
        return 3
    return 4


def component_result(parts: list[dict]) -> dict:
    """Điểm học phần = tổng (điểm thành phần × trọng số), làm tròn 1 số lẻ rồi xếp chữ.

    Trọng số không được bịa: người dùng nhập theo đề cương, hoặc chọn preset QĐ 1473.
    """
    if not parts:
        raise ValueError("Chưa có điểm thành phần")
    weights = []
    for p in parts:
        w = _d(p["weight"])
        if w < 0:
            raise ValueError("Trọng số không được âm")
        weights.append(w)
    total_w = sum(weights, Decimal("0"))
    if abs(total_w - Decimal("1")) > Decimal("0.001"):
        raise ValueError(f"Tổng trọng số phải bằng 1 (đang là {total_w})")
    exam_idx = [i for i, p in enumerate(parts) if p.get("exam")]
    if len(exam_idx) != 1:
        raise ValueError("Cần đúng một cột là điểm thi kết thúc")
    ei = exam_idx[0]
    known = Decimal("0")
    for i, p in enumerate(parts):
        if i == ei:
            continue
        if p.get("score") is None or p.get("score") == "":
            raise ValueError("Nhập đủ các điểm đã có trước khi tính điểm thi cần đạt")
        s = _d(p["score"])
        if s < 0 or s > 10:
            raise ValueError("Điểm thành phần phải từ 0 đến 10")
        known += s * weights[i]
    exam_score = parts[ei].get("score")
    current = None
    if exam_score is not None and exam_score != "":
        s = _d(exam_score)
        if s < 0 or s > 10:
            raise ValueError("Điểm thi phải từ 0 đến 10")
        raw = known + s * weights[ei]
        rounded = round1(raw)
        letter, pts = letter_from_score10(rounded)
        current = {"raw": float(raw), "rounded": float(rounded), "letter": letter, "points": float(pts)}
    needed = []
    w_exam = weights[ei]
    for letter, lo, pts in _BANDS:
        if letter == "F":
            continue
        # Điểm thi nhỏ nhất (bước 0,1) sao cho điểm học phần làm tròn ≥ ngưỡng chữ.
        found = None
        step = Decimal("0.1")
        k = Decimal("0")
        while k <= Decimal("10") + step / 2:
            rounded = round1(known + k * w_exam)
            if rounded >= lo:
                found = k
                break
            k += step
        needed.append({
            "letter": letter,
            "min_course_score": float(lo),
            "points": float(pts),
            "exam_score": None if found is None else float(found),
        })
    return {"current": current, "needed": needed, "known_weighted": float(known)}


def drl_result(scores: dict, discipline: str = "none") -> dict:
    total = 0
    detail = []
    for key, label, cap, article in DRL_CAPS:
        if key not in scores or scores[key] is None or scores[key] == "":
            raise ValueError(f"Thiếu điểm: {label}")
        val = int(scores[key])
        if val < 0 or val > cap:
            raise ValueError(f"{label} chỉ từ 0 đến {cap} (Thông tư 16/2015 {article})")
        total += val
        detail.append({"key": key, "label": label, "cap": cap, "score": val, "article": article})
    raw = _classify_drl(total)
    capped = raw
    note = None
    if discipline == "dinh_chi":
        return {
            "total": total, "raw_band": raw, "band": None, "detail": detail,
            "note": "Điều 10.3 Thông tư 16/2015: đang đình chỉ học tập thì không đánh giá rèn luyện trong thời gian bị đình chỉ.",
        }
    if discipline == "buoc_thoi_hoc":
        return {
            "total": total, "raw_band": raw, "band": None, "detail": detail,
            "note": "Điều 10.4 Thông tư 16/2015: bị kỷ luật buộc thôi học thì không đánh giá kết quả rèn luyện.",
        }
    if discipline == "khien_trach" and total >= 80:
        capped = "Khá"
        note = "Điều 10.1: đang kỷ luật khiển trách, kết quả rèn luyện không được vượt quá loại Khá."
    elif discipline == "canh_cao" and total >= 65:
        capped = "Trung bình"
        note = "Điều 10.2: đang kỷ luật cảnh cáo, kết quả rèn luyện không được vượt quá loại Trung bình."
    return {"total": total, "raw_band": raw, "band": capped, "detail": detail, "note": note}


def _classify_drl(total: int) -> str:
    # Điều 9.2 Thông tư 16/2015.
    if total >= 90:
        return "Xuất sắc"
    if total >= 80:
        return "Tốt"
    if total >= 65:
        return "Khá"
    if total >= 50:
        return "Trung bình"
    if total >= 35:
        return "Yếu"
    return "Kém"


def summarize(payload: dict) -> dict:
    rule = _normalize_rule(payload.get("rule") or "qd1586")
    program = _d(payload.get("program_credits") or 130)
    if program <= 0:
        raise ValueError("Tổng tín chỉ chương trình phải lớn hơn 0")
    discipline = bool(payload.get("discipline_canh_cao"))
    m_override = payload.get("credits_per_year")
    courses = list(payload.get("courses") or [])
    indexed = list(enumerate(courses))
    indexed.sort(key=lambda it: _attempt_sort(it[1], it[0]))

    notes = []
    if rule == "qd1586":
        notes.append("Khóa 2021–2024, Quyết định 1586/QĐ-ĐHSP Điều 8: chưa đạt thì điểm lần học cuối là điểm chính thức; đã đạt rồi học cải thiện thì giữ điểm cao nhất. GPA tích lũy lấy điểm chính thức của học phần đã tích lũy (A+ đến D). Học phần đang F không đưa vào mẫu số tích lũy — điều 9 không viết rõ F còn nợ có ở trong mẫu số hay không, nên máy tính không cộng điểm 0 của F vào GPA tích lũy.")
        notes.append("Cảnh báo theo Điều 10 QĐ 1586 (50% tín chỉ không đạt, điểm học kỳ, điểm tích lũy). Không dùng mốc nợ 24 tín chỉ của Thông tư 08 vì Điều 10 không chép điều đó. Buộc thôi học khi đã bị cảnh báo 2 lần mà kỳ này vẫn thuộc diện cảnh báo.")
    elif rule == "qd2025":
        notes.append("Khóa 2025 trở đi: thang điểm và GPA vẫn theo QĐ 1586 (QĐ 1498 không sửa Điều 8). Trình độ năm học theo mốc 39/78/117 của QĐ 1498 cho chương trình 10 học kỳ. Câu buộc thôi học mới nói «đã bị cảnh báo 03 lần»; Thông tư 08 vẫn khống chế không quá 2 lần liên tiếp. Máy tính chỉ ghi nhận số lần, không tự kết luận buộc thôi học.")
    else:
        notes.append("Khóa 2020 trở về trước (QĐ 1473): điểm tích lũy lấy lần cao nhất trong các lần học; điểm học kỳ tính cả học lại và học cải thiện (Điều 21). Được học lại học phần điểm D (Điều 12.3). Thang điểm không có A+/B+.")
        notes.append("Học kỳ hè được gộp vào học kỳ 2 để xếp hạng học lực (Điều 15). Buộc thôi học khi bị cảnh báo lần thứ 3 (Điều 16.2.a).")
    notes.append("GPA theo năm học không có công thức riêng trong Điều 9 QĐ 1586. Số ở cột năm học là trung bình có trọng số của các lần học trong năm, chỉ để tham khảo.")

    unverified = []
    # Group enrollments by term, preserving sort.
    by_term = {}
    order = []
    loose = []
    for index, course in indexed:
        parsed = _points(course, rule, use_sim=False)
        sim = _points(course, rule, use_sim=True) if course.get("sim_grade") else parsed
        if parsed[0] == "skip":
            unverified.append({"ten_mon": course.get("ten_mon"), "diem_he_4": course.get("diem_he_4"), "reason": parsed[1]})
            continue
        nam, ky = _term_key(course)[2], _term_key(course)[3]
        item = {
            "course": course, "parsed": parsed, "sim": sim, "index": index,
            "credits": _d(course.get("tin_chi") or 0),
            "pass_only": bool(course.get("pass_only")) or parsed[0] == "P",
        }
        if not nam or ky not in _KY_ORDER:
            loose.append(item)
        else:
            key = (nam, ky)
            if key not in by_term:
                order.append(key)
                by_term[key] = []
            by_term[key].append(item)
    order.sort(key=lambda nk: (int(nk[0].split("-")[0]), _KY_ORDER[nk[1]]))

    seen = {}  # key -> list of graded attempts (not pass-only)
    passed_credits = Decimal("0")
    pass_only_credits = Decimal("0")
    semesters = []
    first_main = None
    for nam, ky in order:
        if ky in ("1", "2") and first_main is None:
            first_main = (nam, ky)
        bucket = by_term[(nam, ky)]
        for item in bucket:
            key = _course_key(item["course"]) or f"#{item['index']}"
            seen.setdefault(key, []).append(item)
        snap = _snapshot(seen, rule)
        passed_credits = snap["passed_credits"]
        pass_only_credits = snap["pass_only_credits"]
        standing = _year_standing(passed_credits + pass_only_credits, rule, program, m_override)
        sem_rows = []
        failed_credits = Decimal("0")
        registered = Decimal("0")
        for item in bucket:
            if item["pass_only"]:
                registered += item["credits"]
                letter = item["parsed"][0]
                score10 = item["course"].get("diem_10")
                failed = False
                if letter == "F" or (score10 not in (None, "") and round1(score10) < Decimal("5")):
                    failed = True
                if failed:
                    failed_credits += item["credits"]
                continue
            if item["parsed"][0] in ("I", "X", "R"):
                continue
            registered += item["credits"]
            sem_rows.append((item["credits"], item["parsed"][1]))
            if item["parsed"][0] == "F":
                failed_credits += item["credits"]
        gpa, cred, pts = _weighted(sem_rows)
        semesters.append({
            "nam_hoc": nam, "hoc_ky": ky, "gpa": _num(gpa), "credits": _num(cred),
            "failed_credits": _num(failed_credits), "registered": _num(registered),
            "cumulative_gpa": snap["gpa"], "passed_credits": _num(passed_credits + pass_only_credits),
            "year_standing": standing, "debt_credits": snap["debt"],
            "bucket": bucket, "snap": snap,
        })

    # Loose courses (no term): count only toward cumulative.
    if loose:
        for item in loose:
            key = _course_key(item["course"]) or f"#{item['index']}"
            seen.setdefault(key, []).append(item)
        notes.append("Một số môn chưa chọn năm học/học kỳ: chỉ tính vào GPA tích lũy, không vào GPA học kỳ.")

    final = _snapshot(seen, rule)
    # QĐ 1586: học kỳ phụ tính vào học kỳ chính liền trước. QĐ 1473 gộp hè vào HK2.
    if rule in ("qd1473", "qd1586", "qd2025"):
        semesters = _merge_summer_warnings(semesters, first_main, program)
    else:
        for sem in semesters:
            sem["warning_gpa"] = sem["gpa"]
            sem["warning_failed"] = sem["failed_credits"]
            sem["warning_registered"] = sem["registered"]
            sem["is_main"] = sem["hoc_ky"] in ("1", "2")

    warnings = 0
    consecutive = 0
    max_consecutive = 0
    for sem in semesters:
        reasons = []
        if not sem.get("is_main", sem["hoc_ky"] in ("1", "2")):
            sem["warning"] = False
            sem["warning_reasons"] = ["Học kỳ hè không phải học kỳ chính — Thông tư 08/2021 Điều 11 cảnh báo vào cuối học kỳ chính."]
            consecutive = 0
            continue
        gpa = sem.get("warning_gpa")
        if gpa is not None:
            threshold = Decimal("0.8") if (sem["nam_hoc"], sem["hoc_ky"]) == first_main else Decimal("1.0")
            if _d(gpa) < threshold:
                reasons.append(f"Điểm trung bình học kỳ {gpa} dưới {threshold} (học kỳ đầu khóa 0,8; các học kỳ sau 1,0).")
        cum = sem["cumulative_gpa"]
        if cum is not None:
            cap = CUM_WARN.get(sem["year_standing"], Decimal("1.8"))
            if _d(cum) < cap:
                reasons.append(f"Điểm trung bình tích lũy {cum} dưới {cap} đối với trình độ năm thứ {sem['year_standing']}.")
        reg = _d(sem.get("warning_registered") or 0)
        failed = _d(sem.get("warning_failed") or 0)
        if reg > 0 and failed * 100 > reg * 50:
            cite = "QĐ 1473 không ghi mốc 50%; mốc này lấy từ QĐ 1586 Điều 10 và Thông tư 08 Điều 11." if rule == "qd1473" else "QĐ 1586 Điều 10.2.a."
            if rule != "qd1473":
                reasons.append(f"Tín chỉ không đạt trong học kỳ ({failed}) vượt quá 50% khối lượng đã đăng ký ({reg}) — {cite}")
        sem["warning"] = bool(reasons)
        sem["warning_reasons"] = reasons
        if reasons:
            warnings += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
        sem["warnings_so_far"] = warnings

    retake_second = Decimal("0")
    retake_courses = Decimal("0")
    for attempts in seen.values():
        graded = [a for a in attempts if not a["pass_only"] and a["parsed"][0] in LETTER_POINTS]
        if len(graded) >= 2:
            retake_courses += graded[0]["credits"]
            for extra in graded[1:]:
                retake_second += extra["credits"]
    five_pct = program * Decimal("0.05")
    downgrade_reasons = []
    if retake_second > five_pct:
        downgrade_reasons.append(
            f"Tín chỉ của các lần học lại (từ lần 2) là {retake_second}, vượt 5% của {program} tín chỉ. QĐ 1586 Điều 13 và QĐ 1473 Điều 25 đều hạ một bậc hạng xuất sắc/giỏi; văn bản ví dụ «từ 7 tín chỉ trở lên» với chương trình 130 tín chỉ."
        )
    if discipline:
        downgrade_reasons.append("Đã đánh dấu kỷ luật từ mức cảnh cáo trở lên trong thời gian học (Điều 14.3.b Thông tư 08/2021; Điều 25.2.b QĐ 1473).")

    gpa_final = final["gpa"]
    rank = hang_tot_nghiep(gpa_final) if gpa_final is not None else None
    rank_after = _downgrade(rank) if downgrade_reasons else rank
    dismissal = None
    if rule == "qd2025" and warnings >= 3:
        dismissal = "Đã đủ 3 học kỳ cảnh báo trên dữ liệu đã nhập. QĐ 1498 viết «đã bị cảnh báo 03 lần». Thông tư 08 vẫn không cho quy chế trường vượt quá 2 lần liên tiếp. Đây là ghi nhận để đối chiếu, không phải kết luận buộc thôi học."
    elif warnings >= 3:
        dismissal = "Đã bị cảnh báo 2 lần và kỳ này vẫn thuộc diện cảnh báo (lần thứ 3) trên các học kỳ đã nhập — QĐ 1586 Điều 10.3.a hoặc QĐ 1473 Điều 16.2.a. Chỉ tính trên bảng điểm bạn nhập."

    remaining = program - (final["passed_credits"] + final["pass_only_credits"])
    if remaining < 0:
        remaining = Decimal("0")
    goals = []
    # Điểm chất lượng của các học phần đã đạt (không giữ điểm 0 của học phần sẽ học lại).
    base_points = final["passed_points"]
    base_credits_for_future = final["passed_credits"] + final["pass_only_credits"]
    for label, target in (("Xuất sắc", Decimal("3.60")), ("Giỏi", Decimal("3.20")), ("Khá", Decimal("2.50")), ("Trung bình", Decimal("2.00"))):
        if remaining == 0:
            reached = gpa_final is not None and _d(gpa_final) >= target
            goals.append({"label": label, "target": float(target), "needed": None, "reached": reached})
            continue
        need = (target * (base_credits_for_future + remaining) - base_points) / remaining
        goals.append({
            "label": label,
            "target": float(target),
            "needed": float(round2(need)),
            "possible": need <= Decimal("4"),
            "already": need <= 0,
        })

    years = _year_rows(by_term, loose)
    sem_out = []
    for sem in semesters:
        sem_out.append({k: sem[k] for k in (
            "nam_hoc", "hoc_ky", "gpa", "credits", "failed_credits", "registered",
            "cumulative_gpa", "passed_credits", "year_standing", "debt_credits",
            "warning", "warning_reasons", "warnings_so_far", "warning_gpa",
        ) if k in sem})

    return {
        "rule": rule,
        "program_credits": float(program),
        "cumulative": {
            "gpa": final["gpa"],
            "credits_in_gpa": final["gpa_credits"],
            "passed_credits": final["passed_credits_num"],
            "pass_only_credits": final["pass_only_num"],
            "hoc_luc": hoc_luc(gpa_final),
            "hang_tot_nghiep": rank,
            "hang_sau_ha_bac": rank_after,
            "downgraded": bool(downgrade_reasons),
            "downgrade_reasons": downgrade_reasons,
        },
        "semesters": sem_out,
        "years": years,
        "warnings_count": warnings,
        "max_consecutive_warnings": max_consecutive,
        "dismissal_note": dismissal,
        "debt_credits": final["debt"],
        "retake_credits_second_attempt": float(retake_second),
        "retake_course_credits": float(retake_courses),
        "five_percent": float(five_pct),
        "remaining_credits": float(remaining),
        "goals": goals,
        "unverified": unverified,
        "notes": notes,
        "simulated": _sim_gpa(indexed),
    }


def _sim_gpa(indexed):
    """GPA giả lập theo cùng quy tắc lần học, nhưng điểm chữ giả lập thay điểm thật."""
    cloned = []
    for _i, course in indexed:
        c = dict(course)
        if c.get("sim_grade"):
            c["diem_10"] = None
            c["diem_he_4"] = c["sim_grade"]
        cloned.append(c)
    seen = {}
    for index, course in enumerate(cloned):
        parsed = _points(course, "qd1586", use_sim=False)
        if parsed[0] not in LETTER_POINTS and parsed[0] != "P":
            continue
        item = {
            "course": course, "parsed": parsed, "index": index,
            "credits": _d(course.get("tin_chi") or 0),
            "pass_only": bool(course.get("pass_only")) or parsed[0] == "P",
        }
        key = _course_key(course) or f"#{index}"
        seen.setdefault(key, []).append(item)
    # Giả lập luôn xem lần cuối (thứ tự đã sort ở summarize trước khi gọi).
    snap = _snapshot(seen, "tt08")
    return {"gpa": snap["gpa"], "credits": snap["gpa_credits"]}


def _year_rows(by_term, loose):
    grouped = {}
    for (nam, _ky), items in by_term.items():
        grouped.setdefault(nam, []).extend(items)
    rows = []
    for nam in sorted(grouped):
        acc = []
        for item in grouped[nam]:
            if item["pass_only"] or item["parsed"][0] not in LETTER_POINTS:
                continue
            acc.append((item["credits"], item["parsed"][1]))
        gpa, cred, _pts = _weighted(acc)
        rows.append({"nam_hoc": nam, "gpa": _num(gpa), "credits": _num(cred)})
    return rows


def _snapshot(seen: dict, rule: str) -> dict:
    rows = []
    passed_credits = Decimal("0")
    passed_points = Decimal("0")
    pass_only = Decimal("0")
    debt = Decimal("0")
    for attempts in seen.values():
        graded = [a for a in attempts if not a["pass_only"] and a["parsed"][0] in LETTER_POINTS]
        p_only = [a for a in attempts if a["pass_only"]]
        if p_only:
            last = p_only[-1]
            letter = last["parsed"][0]
            score10 = last["course"].get("diem_10")
            ok = letter == "P" or (letter in LETTER_POINTS and letter != "F") or (
                score10 not in (None, "") and round1(score10) >= Decimal("5")
            )
            if ok:
                pass_only += last["credits"]
        if not graded:
            continue
        if rule == "qd1473":
            best = max(graded, key=lambda a: (a["parsed"][1], _attempt_sort(a["course"], a["index"])))
            chosen = best
        else:
            # Chưa đạt: điểm lần cuối. Đã đạt rồi học cải thiện: giữ điểm cao nhất (QĐ 1586 Điều 8.5).
            chosen = None
            for attempt in graded:
                if chosen is None or chosen["parsed"][0] == "F":
                    chosen = attempt
                elif attempt["parsed"][1] >= chosen["parsed"][1]:
                    chosen = attempt
        if chosen["parsed"][0] == "F":
            debt += chosen["credits"]
            continue
        rows.append((chosen["credits"], chosen["parsed"][1]))
        passed_credits += chosen["credits"]
        passed_points += chosen["parsed"][1] * chosen["credits"]
    gpa, cred, _pts = _weighted(rows)
    return {
        "gpa": _num(gpa),
        "gpa_credits": _num(cred),
        "passed_credits": passed_credits,
        "passed_credits_num": _num(passed_credits),
        "passed_points": passed_points,
        "pass_only_credits": pass_only,
        "pass_only_num": _num(pass_only),
        "debt": _num(debt),
    }


def _merge_summer_warnings(semesters, first_main, program):
    by = {}
    for sem in semesters:
        by.setdefault(sem["nam_hoc"], {}).setdefault(sem["hoc_ky"], sem)
    for sem in semesters:
        sem["is_main"] = sem["hoc_ky"] in ("1", "2")
        sem["warning_gpa"] = sem["gpa"]
        sem["warning_failed"] = sem["failed_credits"]
        sem["warning_registered"] = sem["registered"]
    for nam, group in by.items():
        if "2" in group and "he" in group:
            hk2, he = group["2"], group["he"]
            # Gộp điểm chất lượng học kỳ 2 và hè theo tín chỉ.
            parts = []
            for piece in (hk2, he):
                if piece["gpa"] is not None and _d(piece["credits"]) > 0:
                    parts.append((_d(piece["credits"]), _d(piece["gpa"])))
            gpa, cred, _pts = _weighted(parts)
            hk2["warning_gpa"] = _num(gpa)
            hk2["warning_failed"] = _num(_d(hk2["failed_credits"]) + _d(he["failed_credits"]))
            hk2["warning_registered"] = _num(_d(hk2["registered"]) + _d(he["registered"]))
            he["is_main"] = False
    return semesters


def _num(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value
