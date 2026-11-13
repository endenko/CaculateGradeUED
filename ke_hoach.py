# -*- coding: utf-8 -*-
"""Read a semester plan out of one scanned UED CTĐT table.

The official file is a scan. A course is given a semester only when an "Học kỳ"
column on that page has a number, and the course code sits in that number's
row band. Nothing here guesses a semester from the course name.
"""
from __future__ import annotations

import re

from utils import normalize


def _code(text: str) -> str:
    token = str(text or "").strip().replace("O", "0").replace("o", "0")
    digits = re.sub(r"\D", "", token)
    return digits if re.fullmatch(r"\d{8}", digits) else ""


def _hoc_ky_header(words):
    for word in words:
        text = normalize(word["t"]).replace("φ", "o").replace("ϕ", "o").replace("ø", "o")
        if re.search(r"h\w{0,2}c\s*k[yi]", text):
            return word
    return None


def _semester_number(text: str):
    token = str(text or "").strip()
    if re.fullmatch(r"\d{1,2}", token):
        number = int(token)
        if 1 <= number <= 12:
            return number
    return None


def parse_plan(pages) -> dict:
    """pages: list of word lists, in page order.

    Each word is {t, x, y}. Returns courses with hoc_ky / loai / nhom and the
    credit totals that were actually printed.
    """
    courses = []
    tin_chi_toi_thieu = None
    tu_chon_toi_thieu = None
    exclude_pe = False
    for words in pages:
        blob = normalize(" ".join(w["t"] for w in words))
        if "quoc phong" in blob and ("the chat" in blob or "th cht" in blob or "the cht" in blob):
            exclude_pe = True
        elective = re.search(r"chon(?:\s+\w+){0,2}\s+thi[e]?u\s*(\d{1,2})", blob)
        if elective and tu_chon_toi_thieu is None:
            tu_chon_toi_thieu = int(elective.group(1))
        minimum = re.search(r"tich lu\w*(?:\s+\w+){0,2}\s+thi[e]?u\s*(\d{3})", blob)
        if minimum and tin_chi_toi_thieu is None:
            tin_chi_toi_thieu = int(minimum.group(1))
        header = _hoc_ky_header(words)
        if header is None:
            continue
        markers = []
        for w in words:
            number = _semester_number(w["t"])
            if number is None or w["y"] < header["y"] + 8:
                continue
            if abs(w["x"] - header["x"]) > 40:
                continue
            markers.append({"y": w["y"], "hk": number, "x": w["x"]})
        markers.sort(key=lambda m: m["y"])
        deduped = []
        for marker in markers:
            if deduped and deduped[-1]["hk"] == marker["hk"] and marker["y"] - deduped[-1]["y"] < 25:
                continue
            deduped.append(marker)
        markers = deduped
        if not markers:
            continue
        bands = []
        for index, marker in enumerate(markers):
            top = header["y"] if index == 0 else (markers[index - 1]["y"] + marker["y"]) / 2
            bot = (marker["y"] + markers[index + 1]["y"]) / 2 if index + 1 < len(markers) else 10**9
            bands.append((top, bot, marker["hk"], marker["y"]))
        elective_ys = sorted(w["y"] for w in words if "tu chon" in normalize(w["t"]) and _code(w["t"]) == "")
        for w in words:
            code = _code(w["t"])
            if not code or w["x"] < header["x"] + 20 or w["y"] < header["y"]:
                continue
            band = next((item for item in bands if item[0] <= w["y"] < item[1]), None)
            if band is None:
                continue
            top, _bot, hk, marker_y = band
            # Headings above the học kỳ summary row apply only above that row.
            # Headings below it start the next tự chọn group.
            if w["y"] > marker_y:
                labels = [y for y in elective_ys if marker_y < y < w["y"]]
            else:
                labels = [y for y in elective_ys if top <= y < w["y"]]
            if labels:
                courses.append({
                    "ma_hp": code,
                    "hoc_ky": hk,
                    "loai": "tu_chon",
                    "nhom": f"{hk}.{len(labels)}",
                    "y": w["y"],
                })
            else:
                courses.append({
                    "ma_hp": code,
                    "hoc_ky": hk,
                    "loai": "bat_buoc",
                    "nhom": "",
                    "y": w["y"],
                })
        for marker in markers:
            near = []
            for w in words:
                if abs(w["y"] - marker["y"]) > 14 or w["x"] < header["x"] + 80:
                    continue
                if re.fullmatch(r"\d{1,2}", str(w["t"]).strip()):
                    value = int(w["t"])
                    if value >= 8:
                        near.append(value)
            if near:
                for course in courses:
                    if course["hoc_ky"] == marker["hk"] and "tin_chi_ky" not in course:
                        course["tin_chi_ky"] = min(near)
    # One code can be printed once per plan. Keep the first sighting.
    seen = set()
    unique = []
    for course in sorted(courses, key=lambda c: (c["hoc_ky"], c["y"], c["ma_hp"])):
        if course["ma_hp"] in seen:
            continue
        seen.add(course["ma_hp"])
        unique.append({k: v for k, v in course.items() if k != "y"})
    return {
        "courses": unique,
        "tin_chi_toi_thieu": tin_chi_toi_thieu,
        "tu_chon_toi_thieu": tu_chon_toi_thieu,
        "exclude_pe_qp": exclude_pe,
    }


def is_pe_or_defense(ma_hp: str, ten_mon: str) -> bool:
    name = normalize(ten_mon or "")
    if "giao duc the chat" in name or "giao duc quoc phong" in name:
        return True
    return str(ma_hp or "") in {"00101265", "00101266", "00101267", "00101268", "00201264"}
