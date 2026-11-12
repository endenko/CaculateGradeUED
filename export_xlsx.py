# -*- coding: utf-8 -*-
"""Minimal .xlsx writer (stdlib only) so a 1 GB instance does not need openpyxl."""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape


def _col(index: int) -> str:
    label = ""
    n = index
    while n:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return label


def _sheet_name(name: str, used: set) -> str:
    cleaned = "".join(ch for ch in (name or "Sheet") if ch not in '[]:*?/\\')[:31] or "Sheet"
    base = cleaned
    n = 2
    while cleaned in used:
        suffix = f" {n}"
        cleaned = (base[: 31 - len(suffix)] + suffix)
        n += 1
    used.add(cleaned)
    return cleaned


def _cell(row: int, col: int, value) -> str:
    ref = f"{_col(col)}{row}"
    if value is None or value == "":
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(rows) -> str:
    body = []
    for r_index, row in enumerate(rows, start=1):
        cells = "".join(_cell(r_index, c_index, value) for c_index, value in enumerate(row, start=1))
        body.append(f'<row r="{r_index}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(body)}</sheetData></worksheet>'
    )


def build_xlsx(sheets) -> bytes:
    """sheets: list of (name, rows). Each row is a list of numbers or strings."""
    buf = io.BytesIO()
    used = set()
    names = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        workbook_sheets = []
        rels = []
        for index, (name, rows) in enumerate(sheets, start=1):
            sheet_name = _sheet_name(name, used)
            names.append(sheet_name)
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows or []))
            workbook_sheets.append(
                f'<sheet name="{escape(sheet_name)}" sheetId="{index}" r:id="rId{index}"/>'
            )
            rels.append(
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(workbook_sheets)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels) + "</Relationships>",
        )
    return buf.getvalue()


def grade_sheets(payload: dict):
    """Turn the three tables the UI already shows into worksheet rows."""
    bang1 = [["Môn học", "Tín chỉ", "Điểm chữ", "Điểm 10", "Năm học", "Học kỳ", "Lần"]]
    for course in payload.get("bang1") or []:
        bang1.append([
            course.get("ten_mon") or "",
            course.get("tin_chi") if course.get("tin_chi") is not None else "",
            course.get("diem_he_4") or "",
            course.get("diem_10") if course.get("diem_10") not in (None, "") else "",
            course.get("nam_hoc") or "",
            course.get("hoc_ky") or "",
            course.get("lan") if course.get("lan") is not None else "",
        ])
    bang2 = [["Môn học", "Tín chỉ", "Chuyên cần", "Giữa kỳ", "Cuối kỳ", "Điểm 10", "Điểm chữ", "Hệ 4", "Năm học", "Học kỳ"]]
    for course in payload.get("bang2") or []:
        bang2.append([
            course.get("ten_mon") or "",
            course.get("tin_chi") if course.get("tin_chi") is not None else "",
            course.get("bp") if course.get("bp") not in (None, "") else "",
            course.get("gk") if course.get("gk") not in (None, "") else "",
            course.get("ck") if course.get("ck") not in (None, "") else "",
            course.get("score10") if course.get("score10") not in (None, "") else "",
            course.get("letter") or "",
            course.get("points") if course.get("points") not in (None, "") else "",
            course.get("nam_hoc") or "",
            course.get("hoc_ky") or "",
        ])
    summary = [["Chỉ số", "Giá trị"]]
    for key, label in (
        ("cpa", "CPA"),
        ("gpa_gia_lap", "GPA giả lập"),
        ("chenh_lech", "Chênh lệch"),
        ("tin_chi_dat", "Tín chỉ đã đạt"),
        ("tin_chi_muc_tieu", "Tín chỉ mục tiêu"),
    ):
        if key in (payload.get("summary") or {}):
            summary.append([label, payload["summary"][key]])
    return [("Điểm tổng", bang1), ("Điểm học phần", bang2), ("Tổng kết", summary)]
