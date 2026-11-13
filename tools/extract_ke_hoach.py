# -*- coding: utf-8 -*-
"""OCR the official UED CTĐT scans and write data/ke_hoach_dao_tao.json.

Only semesters printed in the Học kỳ column are stored. Run manually;
the web app just reads the JSON.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rapidocr import RapidOCR

from ke_hoach import parse_plan
from tools.build_ued_courses import NGANH, NGANH24

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "hoc_phan_ued.csv")
OUT_PATH = os.path.join(ROOT, "data", "ke_hoach_dao_tao.json")


def _words(result):
    boxes = result.boxes
    texts = result.txts
    if boxes is None or texts is None or len(boxes) == 0:
        return []
    words = []
    for box, text in zip(boxes, texts):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        words.append({"t": str(text).strip(), "x": (min(xs) + max(xs)) / 2, "y": (min(ys) + max(ys)) / 2})
    return words


def _ocr_pdf(path, ocr):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.check_call(["pdftoppm", "-png", "-r", "110", path, os.path.join(tmp, "p")], stdout=subprocess.DEVNULL)
        pages = []
        names = sorted(n for n in os.listdir(tmp) if n.endswith(".png"))
        for name in names:
            pages.append(_words(ocr(os.path.join(tmp, name))))
        return pages


def _catalog():
    by_prog = {}
    by_code = {}
    with open(CSV_PATH, encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            by_prog.setdefault(row["nganh"], {})[row["ma_hp"]] = row
            by_code.setdefault(row["ma_hp"], row)
    return by_prog, by_code


def _urls():
    found = []
    y25 = os.path.join(ROOT, "tools", "ued_ctdt_2025_urls.txt")
    y24 = os.path.join(ROOT, "tools", "ued_ctdt_2024_urls.txt")
    for path, table, year in ((y25, NGANH, 2025), (y24, NGANH24, 2024)):
        for line in open(path, encoding="utf-8"):
            url = line.strip()
            if not url.endswith(".pdf"):
                continue
            stem = os.path.splitext(os.path.basename(url))[0]
            nganh = table.get(stem)
            if not nganh:
                continue
            if year == 2024:
                nganh = nganh if nganh.endswith("(khóa 2024)") else nganh + " (khóa 2024)"
            found.append((nganh, url, year))
    # Later URL for the same program wins (the 2026/01 file replaces 2025/11).
    unique = {}
    for item in found:
        unique[item[0]] = item
    return list(unique.values())


def main():
    by_prog, by_code = _catalog()
    ocr = RapidOCR()
    out = {}
    skipped = []
    cache = "/tmp/ctdt-pdf"
    os.makedirs(cache, exist_ok=True)
    for nganh, url, year in _urls():
        dest = os.path.join(cache, f"{year}-{nganh[:40].replace(' ', '_')}.pdf")
        if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
            subprocess.check_call(["curl", "-fsSL", "-o", dest, url])
        plan = parse_plan(_ocr_pdf(dest, ocr))
        rows = []
        catalog = by_prog.get(nganh, {})
        for course in plan["courses"]:
            known = catalog.get(course["ma_hp"]) or by_code.get(course["ma_hp"])
            if not known:
                continue
            rows.append({
                "ma_hp": course["ma_hp"],
                "ten_mon": known["ten_mon"],
                "tin_chi": int(known["tin_chi"]) if str(known.get("tin_chi") or "").isdigit() else None,
                "hoc_ky": course["hoc_ky"],
                "loai": course["loai"],
                "nhom": course["nhom"],
            })
        semesters = sorted({row["hoc_ky"] for row in rows})
        if len(rows) < 15 or len(semesters) < 3:
            skipped.append((nganh, len(rows), semesters[:8]))
            print("skip", nganh, len(rows), semesters[:8], flush=True)
            continue
        ky_totals = {}
        for course in plan["courses"]:
            if course.get("tin_chi_ky") and course["hoc_ky"] not in ky_totals:
                ky_totals[course["hoc_ky"]] = course["tin_chi_ky"]
        out[nganh] = {
            "nguon": url,
            "khoa_tuyen_sinh": year,
            "partial": 1 not in semesters,
            "tin_chi_toi_thieu": plan["tin_chi_toi_thieu"],
            "tu_chon_toi_thieu": plan["tu_chon_toi_thieu"],
            "exclude_pe_qp": plan["exclude_pe_qp"],
            "tin_chi_ky": {str(k): v for k, v in ky_totals.items()},
            "courses": rows,
        }
        print("ok", nganh, len(rows), "hk", semesters, "min", plan["tin_chi_toi_thieu"], "elect", plan["tu_chon_toi_thieu"], flush=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
    print("wrote", len(out), "skipped", len(skipped))


if __name__ == "__main__":
    main()
