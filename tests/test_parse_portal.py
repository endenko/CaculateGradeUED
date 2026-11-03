# -*- coding: utf-8 -*-
import os
import unittest

import app
from solver import semester_options


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "portal_hk2_2024.png")


class ParseTests(unittest.TestCase):
    def test_simple_name_credits_letter(self):
        rows = app.parse_computer(["Giai tich 1   3   A"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["tin_chi"], 3)
        self.assertEqual(row["diem_he_4"], "A")
        self.assertIsNone(row["diem_10"])
        self.assertFalse(row["in_progress"])
        self.assertIn("Giải tích 1", row["ten_mon"])

    def test_simple_name_credits_score(self):
        rows = app.parse_computer(["Toan roi rac  4  8.5  B+"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tin_chi"], 4)
        self.assertEqual(rows[0]["diem_10"], 8.5)
        self.assertEqual(rows[0]["diem_he_4"], "A")

    def test_portal_lines_term_retake_and_blank_score(self):
        lines = [
            "Hgc ky: 2 - Näm hgc: 2024 - 2025 Diém HP he 10",
            "1 00101268 Giao duc the chat 4 23-0107 1",
            "2 21221903 Chu nghia xa hoi khoa hoc 23-0110 2 8,1 B+",
            "3 31221010 An toan thong tin 23-0101 2 7,5 8,6 B A",
            "Tong so tin chi hoc ky 22.00 So tin chi tich luy 74",
            "Diem trung binh hoc ky he 4 3.81",
        ]
        term = app.extract_term(lines)
        self.assertEqual(term, {"hoc_ky": "2", "nam_hoc": "2024-2025"})
        self.assertIsNone(app.extract_term(["Hoc ky: 2"]))
        rows = app.parse_computer(lines)
        by_raw = {r["raw_name"]: r for r in rows}
        self.assertTrue(any(r["in_progress"] and r["diem_he_4"] is None for r in rows))
        done = next(r for r in rows if r["diem_10"] == 8.1)
        self.assertEqual(done["diem_he_4"], "B+")
        self.assertEqual(done["lan"], 1)
        self.assertEqual(done["tin_chi"], 2)
        retake = next(r for r in rows if r["lan"] == 2)
        self.assertEqual(retake["diem_10"], 8.6)
        self.assertEqual(retake["diem_he_4"], "A")
        self.assertFalse(any("trung binh" in app._fold_line(r["raw_name"]) for r in rows))
        self.assertIn("the chat", app._fold_line(next(r["raw_name"] for r in rows if r["in_progress"])))
        self.assertEqual(len(by_raw), 3)

    def test_portal_screenshot_fixture(self):
        from ocr import engines
        words = engines.computer_words(FIXTURE)
        lines = app.reconstruct_lines(words, "computer")
        term = app.extract_term(lines)
        rows = app.parse_computer(lines)
        self.assertEqual(term, {"hoc_ky": "2", "nam_hoc": "2024-2025"})
        self.assertGreaterEqual(len(rows), 8)
        self.assertTrue(any(r["in_progress"] for r in rows))
        scored = [r for r in rows if r["diem_10"] is not None]
        self.assertGreaterEqual(len(scored), 7)
        self.assertTrue(any(abs((r["diem_10"] or 0) - 9.2) < 0.05 and r["diem_he_4"] == "A" for r in rows))
        self.assertTrue(all(r["diem_he_4"] != "F" or r["diem_10"] is not None for r in rows if not r["in_progress"]))
        names = " | ".join(r["ten_mon"] for r in rows)
        self.assertNotIn("trung bình", names.lower())


class SemesterOptionTests(unittest.TestCase):
    def test_at_most_five_easiest_first(self):
        table2 = [
            {"id": "j", "ten_mon": "Java", "credits": 3, "bp": 8, "gk": 8, "ck": None, "points": None},
            {"id": "t", "ten_mon": "Toán rời rạc", "credits": 3, "bp": 7, "gk": 7, "ck": None, "points": None},
        ]
        opts = semester_options(table2, target=3.2)
        self.assertLessEqual(len(opts), 5)
        self.assertGreaterEqual(len(opts), 2)
        self.assertTrue(all(o["feasible"] for o in opts))
        self.assertGreaterEqual(opts[0]["gpa"], 3.2)
        self.assertLessEqual(opts[0]["max_ck"], opts[-1]["max_ck"])
        summary = opts[0]["summary"]
        self.assertIn("Java", summary)
        self.assertIn("Toán rời rạc", summary)
        for course in opts[0]["courses"]:
            self.assertIsNotNone(course["min_ck"])
            self.assertFalse(course["ck_over"])

    def test_impossible_is_a_single_option(self):
        table2 = [{"id": "m", "ten_mon": "Sử", "credits": 3, "bp": 0, "gk": 0, "ck": None, "points": None}]
        opts = semester_options(table2, target=3.6)
        self.assertEqual(len(opts), 1)
        self.assertFalse(opts[0]["feasible"])
        self.assertTrue(opts[0]["courses"][0]["ck_over"])


if __name__ == "__main__":
    unittest.main()
