# -*- coding: utf-8 -*-
import io
import unittest
import zipfile

import export_xlsx


class XlsxTests(unittest.TestCase):
    def test_grade_workbook_keeps_vietnamese_and_numbers(self):
        payload = {
            "bang1": [{
                "ten_mon": "Triết học Mác - Lênin",
                "tin_chi": 3,
                "diem_he_4": "A",
                "diem_10": 9.0,
                "nam_hoc": "2024-2025",
                "hoc_ky": "1",
                "lan": 1,
            }],
            "bang2": [{
                "ten_mon": "Giải tích",
                "tin_chi": 3,
                "bp": 8,
                "gk": 7,
                "ck": 9,
                "score10": 8.2,
                "letter": "B+",
                "points": 3.5,
                "nam_hoc": "2025-2026",
                "hoc_ky": "2",
            }],
            "summary": {"cpa": "3.50", "gpa_gia_lap": "3.60", "chenh_lech": "+0.10", "tin_chi_dat": 3, "tin_chi_muc_tieu": 130},
        }
        blob = export_xlsx.build_xlsx(export_xlsx.grade_sheets(payload))
        with zipfile.ZipFile(io.BytesIO(blob)) as book:
            names = book.namelist()
            self.assertIn("xl/workbook.xml", names)
            sheet1 = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
            sheet2 = book.read("xl/worksheets/sheet2.xml").decode("utf-8")
            sheet3 = book.read("xl/worksheets/sheet3.xml").decode("utf-8")
            workbook = book.read("xl/workbook.xml").decode("utf-8")
        self.assertIn("Triết học Mác - Lênin", sheet1)
        self.assertIn(">3<", sheet1)
        self.assertIn("Giải tích", sheet2)
        self.assertIn("CPA", sheet3)
        self.assertIn("Điểm tổng", workbook)
        self.assertIn("Điểm học phần", workbook)
        self.assertIn("Tổng kết", workbook)


if __name__ == "__main__":
    unittest.main()
