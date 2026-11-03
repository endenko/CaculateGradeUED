# -*- coding: utf-8 -*-
import unittest

from regulations import (
    component_result, drl_result, letter_from_score10, round1, summarize,
)


class LetterTests(unittest.TestCase):
    def test_official_bands(self):
        self.assertEqual(letter_from_score10(9.5)[0], "A+")
        self.assertEqual(letter_from_score10(9.2)[0], "A")
        self.assertEqual(letter_from_score10(8.45)[0], "A")
        self.assertEqual(letter_from_score10(8.44)[0], "B+")
        self.assertEqual(letter_from_score10(8.0)[0], "B+")
        self.assertEqual(letter_from_score10(8.0)[1], round1("3.5"))
        self.assertEqual(letter_from_score10(7.0)[0], "B")
        self.assertEqual(letter_from_score10(6.5)[0], "C+")
        self.assertEqual(letter_from_score10(5.5)[0], "C")
        self.assertEqual(letter_from_score10(5.0)[0], "D+")
        self.assertEqual(letter_from_score10(4.0)[0], "D")
        self.assertEqual(letter_from_score10(3.9)[0], "F")
        self.assertEqual(letter_from_score10(8.2, "qd1473")[0], "B")


class SummaryTests(unittest.TestCase):
    def _course(self, name, score, credits=3, nam="2025-2026", ky="1", lan=1):
        return {"ten_mon": name, "diem_10": score, "tin_chi": credits, "nam_hoc": nam, "hoc_ky": ky, "lan": lan}

    def test_tt08_last_attempt_replaces_f(self):
        out = summarize({
            "rule": "tt08",
            "program_credits": 130,
            "courses": [
                self._course("Giải tích", 3.0, ky="1", lan=1),
                self._course("Giải tích", 8.5, ky="2", lan=2),
                self._course("Triết", 7.0, ky="1"),
            ],
        })
        # Chỉ còn A (4) và B (3), mỗi môn 3 TC → GPA (12+9)/6 = 3.5
        self.assertEqual(out["cumulative"]["gpa"], 3.5)
        self.assertEqual(out["debt_credits"], 0)
        self.assertEqual(out["cumulative"]["hoc_luc"], "Giỏi")
        self.assertTrue(out["cumulative"]["downgraded"] is False or out["retake_course_credits"] <= out["five_percent"])

    def test_tt08_retake_downgrade(self):
        courses = [self._course(f"M{i}", 8.5, credits=3) for i in range(10)]
        courses.append(self._course("Nợ", 3, credits=10, ky="1", lan=1))
        courses.append(self._course("Nợ", 8.5, credits=10, ky="2", lan=2))
        out = summarize({"rule": "tt08", "program_credits": 130, "courses": courses, "discipline_canh_cao": False})
        self.assertEqual(out["retake_course_credits"], 10)
        self.assertTrue(out["cumulative"]["downgraded"])
        self.assertEqual(out["cumulative"]["hang_tot_nghiep"], "Xuất sắc")
        self.assertEqual(out["cumulative"]["hang_sau_ha_bac"], "Giỏi")

    def test_qd1473_keeps_highest_and_drops_f_from_cumulative(self):
        out = summarize({
            "rule": "qd1473",
            "program_credits": 130,
            "courses": [
                self._course("Vật lý", 5.5, ky="1", lan=1),
                self._course("Vật lý", 8.0, ky="2", lan=2),
                self._course("Hóa", 3.0, ky="1"),
            ],
        })
        # Cao nhất của Vật lý là B=3; Hóa F không vào mẫu số tích lũy → GPA 3.0
        self.assertEqual(out["cumulative"]["gpa"], 3.0)
        self.assertEqual(out["debt_credits"], 3.0)

    def test_warning_first_semester(self):
        out = summarize({
            "rule": "tt08",
            "program_credits": 130,
            "courses": [self._course("A", 3.0, credits=15, ky="1"), self._course("B", 8.5, credits=15, nam="2026-2027", ky="1")],
        })
        hk1 = out["semesters"][0]
        self.assertTrue(hk1["warning"])
        self.assertTrue(any("0.8" in r for r in hk1["warning_reasons"]))

    def test_plus_letter_counts_on_1586(self):
        out = summarize({
            "rule": "qd1586",
            "courses": [{"ten_mon": "X", "diem_he_4": "B+", "tin_chi": 3, "nam_hoc": "2025-2026", "hoc_ky": "1"}],
        })
        self.assertEqual(out["cumulative"]["gpa"], 3.5)

    def test_improvement_keeps_higher_score(self):
        out = summarize({
            "rule": "qd1586",
            "courses": [
                self._course("Môn", 8.6, ky="1", lan=1),
                self._course("Môn", 7.2, ky="2", lan=2),
            ],
        })
        self.assertEqual(out["cumulative"]["gpa"], 4.0)

    def test_target_remaining(self):
        out = summarize({
            "rule": "tt08",
            "program_credits": 10,
            "courses": [self._course("A", 8.5, credits=4)],
        })
        gioi = next(g for g in out["goals"] if g["label"] == "Giỏi")
        # (3.2*10 - 16) / 6 = 2.666... → 2.67
        self.assertEqual(gioi["needed"], 2.67)


class ComponentTests(unittest.TestCase):
    def test_preset_and_needed_exam(self):
        parts = [
            {"weight": 0.1, "score": 8, "exam": False},
            {"weight": 0.1, "score": 8, "exam": False},
            {"weight": 0.3, "score": 7, "exam": False},
            {"weight": 0.5, "score": 9, "exam": True},
        ]
        out = component_result(parts)
        # 0.1*8 + 0.1*8 + 0.3*7 + 0.5*9 = 0.8+0.8+2.1+4.5 = 8.2 → B
        self.assertEqual(out["current"]["letter"], "B+")
        need_a = next(n for n in out["needed"] if n["letter"] == "A")
        self.assertIsNotNone(need_a["exam_score"])
        self.assertGreaterEqual(need_a["exam_score"], 9)

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            component_result([
                {"weight": 0.2, "score": 8, "exam": False},
                {"weight": 0.5, "score": 8, "exam": True},
            ])


class DrlTests(unittest.TestCase):
    def test_bands_and_cap(self):
        scores = {"hoc_tap": 20, "noi_quy": 25, "hoat_dong": 20, "cong_dan": 25, "can_bo": 10}
        self.assertEqual(drl_result(scores)["band"], "Xuất sắc")
        capped = drl_result(scores, discipline="khien_trach")
        self.assertEqual(capped["band"], "Khá")
        self.assertEqual(drl_result({"hoc_tap": 15, "noi_quy": 15, "hoat_dong": 10, "cong_dan": 10, "can_bo": 0})["band"], "Trung bình")

    def test_rejects_over_cap(self):
        with self.assertRaises(ValueError):
            drl_result({"hoc_tap": 21, "noi_quy": 0, "hoat_dong": 0, "cong_dan": 0, "can_bo": 0})


if __name__ == "__main__":
    unittest.main()
