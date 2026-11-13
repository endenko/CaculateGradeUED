# -*- coding: utf-8 -*-
"""Parse a UED lịch thi or thời khoá biểu screenshot from OCR word boxes.

Words are {text, x, y} with x/y at the box centre. An "x" is placed in a
tiết or tuần column by its x coordinate, not by assuming every week is filled.
"""
from __future__ import annotations

import re

from utils import normalize

# Giờ tiết mặc định, sửa được trước khi lưu. Không thấy bảng giờ chính thức
# của UED trên ued.udn.vn khi đối chiếu, nên đây là khung 50 phút thường gặp
# ở Đại học Đà Nẵng (nghỉ 5 phút, ra chơi giữa tiết 3–4 và 8–9).
PERIODS = {
    1: ("07:00", "07:50"),
    2: ("07:55", "08:45"),
    3: ("08:50", "09:40"),
    4: ("09:55", "10:45"),
    5: ("10:50", "11:40"),
    6: ("13:00", "13:50"),
    7: ("13:55", "14:45"),
    8: ("14:50", "15:40"),
    9: ("15:55", "16:45"),
    10: ("16:50", "17:40"),
    11: ("18:00", "18:50"),
    12: ("18:55", "19:45"),
    13: ("19:50", "20:40"),
    14: ("20:45", "21:35"),
    15: ("21:40", "22:30"),
}

_DAY = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "thu 2": 2, "thu 3": 3, "thu 4": 4, "thu 5": 5, "thu 6": 6, "thu 7": 7,
    "cn": 8, "chu nhat": 8,
}


def period_span(numbers):
    """Contiguous tiết runs -> (start, end, periods)."""
    nums = sorted({int(n) for n in numbers if int(n) in PERIODS})
    if not nums:
        return []
    runs = []
    start = prev = nums[0]
    group = [start]
    for num in nums[1:]:
        if num == prev + 1:
            group.append(num)
            prev = num
            continue
        runs.append((PERIODS[group[0]][0], PERIODS[group[-1]][1], group))
        group = [num]
        prev = num
    runs.append((PERIODS[group[0]][0], PERIODS[group[-1]][1], group))
    return runs


def _explode(words):
    """Split an OCR blob like '1 2 3' or 'x x' into one word per mark."""
    out = []
    for word in words:
        text = _text(word)
        parts = text.split()
        if len(parts) > 1 and all(re.fullmatch(r"\d{1,2}|[xX×]", part) for part in parts):
            width = max(24, 14 * len(text))
            step = width / len(parts)
            start = word["x"] - width / 2 + step / 2
            for index, part in enumerate(parts):
                out.append({"text": part, "x": start + index * step, "y": word["y"]})
        else:
            out.append({"text": text, "x": word["x"], "y": word["y"]})
    return out


def _rows(words, tol=16):
    words = _explode(words)
    ordered = sorted(words, key=lambda w: (w["y"], w["x"]))
    rows = []
    for word in ordered:
        if rows and abs(word["y"] - rows[-1][0]["y"]) <= tol:
            rows[-1].append(word)
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w["x"])
    return rows


def _blob(words):
    return normalize(" ".join(w.get("text") or w.get("t") or "" for w in words))


def _text(word):
    return str(word.get("text") or word.get("t") or "").strip()


def _code(text):
    digits = re.sub(r"\D", "", str(text or ""))
    return digits if re.fullmatch(r"\d{8}", digits) else ""


def _day(text):
    key = normalize(text).strip()
    if key in _DAY:
        return _DAY[key]
    match = re.search(r"thu\s*([2-7])", key)
    if match:
        return int(match.group(1))
    if key in {"cn", "chu nhat"}:
        return 8
    return None


def _header_kind(text):
    key = normalize(text)
    if key in {"stt", "tt"}:
        return "stt"
    if "ma hoc" in key or key in {"ma hp", "ma"}:
        return "ma"
    if "ten hoc" in key or key == "ten":
        return "ten"
    if "hinh thuc" in key:
        return "hinh_thuc"
    if key in {"gio", "giờ"} or key == "gio":
        return "gio"
    if "ngay" in key:
        return "ngay"
    if key == "buoi" or key.startswith("buoi"):
        return "buoi"
    if "nhom hoc" in key:
        return "nhom"
    if "nhom thi" in key:
        return "nhom_thi"
    if "phong" in key:
        return "phong"
    if "si so" in key:
        return "si_so"
    if "can bo" in key or "giang vien" in key:
        return "giang_vien"
    if key in {"thu", "thu "}:
        return "thu"
    return ""


def _nearest(headers, x):
    if not headers:
        return ""
    kind, hx = min(headers, key=lambda item: abs(item[1] - x))
    pitch = 80
    xs = sorted(h[1] for h in headers)
    if len(xs) > 1:
        gaps = [b - a for a, b in zip(xs, xs[1:]) if b > a]
        if gaps:
            pitch = sorted(gaps)[len(gaps) // 2]
    if abs(hx - x) > max(pitch, 40):
        return ""
    return kind


def _term_from_blob(blob):
    nam = ""
    ky = ""
    year = re.search(r"nam hoc\s+(\d{4})\s+(\d{4})", blob)
    if year:
        nam = f"{year.group(1)}-{year.group(2)}"
    term = re.search(r"hoc k[yi]\s+(\d)", blob)
    if term:
        ky = term.group(1)
    return nam, ky


def parse_exam(words) -> dict:
    rows = _rows(words)
    blob = _blob(words)
    nam, ky = _term_from_blob(blob)
    header_i = None
    headers = []
    for index, row in enumerate(rows):
        kinds = []
        for word in row:
            kind = _header_kind(_text(word))
            if kind:
                kinds.append((kind, word["x"]))
        if len({k for k, _x in kinds}) >= 3:
            header_i = index
            headers = kinds
            break
    parsed = []
    if header_i is None:
        return {"rows": [], "nam_hoc": nam, "hoc_ky": ky}
    for row in rows[header_i + 1:]:
        cells = {}
        for word in row:
            kind = _nearest(headers, word["x"])
            if re.search(r"[A-Z]\d-\d{2,3}", _text(word)):
                kind = "phong"
            if not kind:
                continue
            cells.setdefault(kind, []).append(_text(word))
        joined = " ".join(_text(w) for w in row)
        code = ""
        for part in cells.get("ma", []) + [joined]:
            code = _code(part)
            if code:
                break
        if not code and not cells.get("ten"):
            continue
        gio = ""
        for part in cells.get("gio", []):
            found = re.search(r"(\d{1,2})[:h](\d{2})", part)
            if found:
                gio = f"{int(found.group(1)):02d}:{found.group(2)}"
        ngay = ""
        for part in cells.get("ngay", []) + [joined]:
            found = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", part)
            if found:
                ngay = f"{int(found.group(1)):02d}-{int(found.group(2)):02d}-{found.group(3)}"
                break
        buoi = ""
        for part in cells.get("buoi", []):
            key = normalize(part)
            if "sang" in key:
                buoi = "Sáng"
            elif "chieu" in key:
                buoi = "Chiều"
            elif "toi" in key:
                buoi = "Tối"
        parsed.append({
            "ma_hp": code,
            "ten_mon": " ".join(cells.get("ten", [])).strip(),
            "hinh_thuc": " ".join(cells.get("hinh_thuc", [])).strip(),
            "gio": gio,
            "ngay": ngay,
            "buoi": buoi,
            "nhom": " ".join(cells.get("nhom", [])).strip(),
            "nhom_thi": " ".join(cells.get("nhom_thi", [])).strip(),
            "phong": " ".join(cells.get("phong", [])).strip(),
        })
    return {"rows": parsed, "nam_hoc": nam, "hoc_ky": ky}


def _number_line(rows):
    best = None
    for row in rows:
        nums = []
        for word in row:
            if re.fullmatch(r"\d{1,2}", _text(word)):
                value = int(_text(word))
                if 1 <= value <= 22:
                    nums.append((value, word["x"], word["y"]))
        if len(nums) >= 5 and (best is None or len(nums) > len(best)):
            best = nums
    return best or []


def _split_grids(nums):
    ordered = sorted(nums, key=lambda item: item[1])
    if len(ordered) < 5:
        return ordered, []
    gaps = []
    for left, right in zip(ordered, ordered[1:]):
        gaps.append((right[1] - left[1], left, right))
    split_at = max(gaps, key=lambda item: item[0])
    if split_at[0] < 40:
        return ordered, []
    left = [item for item in ordered if item[1] <= split_at[1][1]]
    right = [item for item in ordered if item[1] >= split_at[2][1]]
    return left, right


def _marks(row, headers):
    if len(headers) < 2:
        return []
    xs = [item[1] for item in headers]
    pitch = sorted(b - a for a, b in zip(xs, xs[1:]) if b > a)
    limit = (pitch[len(pitch) // 2] * 1.05) if pitch else 18
    found = []
    for word in row:
        token = normalize(_text(word))
        if token not in {"x", "×", "v"}:
            continue
        number, hx, _y = min(headers, key=lambda item: abs(item[1] - word["x"]))
        if abs(hx - word["x"]) <= limit:
            found.append(number)
    return sorted(set(found))


def _week_start(blob):
    match = re.search(r"tuan\s*1\s*bat dau\D+(\d{1,2})\s+(\d{1,2})\s+(\d{4})", blob)
    if not match:
        return ""
    return f"{match.group(3)}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"


def parse_timetable(words) -> dict:
    rows = _rows(words)
    blob = _blob(words)
    nums = _number_line(rows)
    periods, weeks = _split_grids(nums)
    if periods and max(n for n, _x, _y in periods) > 16 and not weeks:
        # A single 1..19 run is the week grid; tiết headers were missed.
        weeks, periods = periods, []
    parsed = []
    for row in rows:
        day = None
        code = ""
        name_parts = []
        room = ""
        lecturer = ""
        group = ""
        size = ""
        buoi = ""
        for word in row:
            text = _text(word)
            if day is None:
                day = _day(text)
            if not code:
                code = _code(text)
            key = normalize(text)
            if "sang" == key:
                buoi = "Sáng"
            elif "chieu" == key:
                buoi = "Chiều"
            elif "toi" == key:
                buoi = "Tối"
        if day is None and not code:
            continue
        # Text that is not a mark, not a pure tiết/tuần index, stays as fields
        # by rough x: code left, name middle, room/lecturer between name and grids.
        grid_x = min((item[1] for item in periods), default=10**9)
        for word in row:
            text = _text(word)
            key = normalize(text)
            if key in {"sang", "chieu", "toi"} or _day(text) or _code(text):
                continue
            if word["x"] >= grid_x - 15:
                continue
            if re.fullmatch(r"\d{1,3}", text) and not group:
                size = text
                continue
            if re.fullmatch(r"\d{2}-\d{3,4}", text):
                group = text
                continue
            if re.search(r"[A-Z]\d-\d{2,3}", text) or re.search(r"\b[A-Z]\d-", text):
                room = text
                continue
            if len(text) > 2:
                name_parts.append(text)
        period_marks = _marks(row, periods)
        week_marks = _marks(row, weeks)
        if not period_marks and not code:
            continue
        name = " ".join(name_parts).strip(" |-")
        for start, end, group_periods in period_span(period_marks) or [("", "", [])]:
            parsed.append({
                "thu": day,
                "ma_hp": code,
                "nhom": group,
                "si_so": size,
                "ten_mon": name,
                "buoi": buoi,
                "tiet": group_periods,
                "start": start,
                "end": end,
                "giang_vien": lecturer,
                "phong": room,
                "tuan": week_marks,
            })
    return {"rows": [row for row in parsed if row["ma_hp"] or row["ten_mon"]], "week_start": _week_start(blob), "periods": PERIODS}


def attach_catalog(rows):
    """Prefer the course database when the code or the name matches."""
    import db
    fixed = []
    for row in rows:
        item = dict(row)
        code = item.get("ma_hp") or ""
        name = item.get("ten_mon") or ""
        hit = db.by_code(code) if code else None
        if hit:
            item["ma_hp"] = code
            item["ten_mon"] = hit["ten_mon"]
            item["match"] = "ma_hp"
        elif name:
            found = db.search_subjects(name, limit=1)
            if found:
                item["ten_mon"] = found[0]["ten_mon"]
                if found[0].get("ma_hp") and not item.get("ma_hp"):
                    item["ma_hp"] = found[0]["ma_hp"]
                item["match"] = "ten"
            else:
                item["match"] = ""
        else:
            item["match"] = ""
        fixed.append(item)
    return fixed
