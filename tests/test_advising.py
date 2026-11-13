# -*- coding: utf-8 -*-
import unittest

import advising


def course(name, letter, credits=3, ky="1", nam="2024-2025", lan=1, score=None):
    row = {
        "ten_mon": name, "tin_chi": credits, "diem_he_4": letter,
        "nam_hoc": nam, "hoc_ky": ky, "lan": lan,
    }
    if score is not None:
        row["diem_10"] = score
    return row


class RetakeTests(unittest.TestCase):
    def test_ranks_credit_weighted_gain_and_keeps_the_higher_grade(self):
        courses = [
            course("Giải tích", "D"),
            course("Vật lý", "F"),
            course("Hóa", "A"),
        ]
        out = advising.retake_suggestions(courses, target="A")
        self.assertEqual(out["cpa_now"], 2.5)
        self.assertEqual(out["singles"][0]["ten_mon"], "Giải tích")
        self.assertGreater(out["singles"][0]["gain"], out["singles"][1]["gain"])
        self.assertEqual(out["singles"][0]["cpa_after"], 4.0)
        names = {item["ten_mon"] for item in out["singles"]}
        self.assertNotIn("Hóa", names)
        self.assertTrue(out["pairs"])
        self.assertGreaterEqual(out["pairs"][0]["gain"], out["singles"][0]["gain"])

    def test_rejects_unknown_target(self):
        with self.assertRaises(ValueError):
            advising.retake_suggestions([course("X", "D")], target="C")


class ScholarshipTests(unittest.TestCase):
    def _full(self, letter="A", failed=False):
        rows = [course(f"M{i}", letter) for i in range(5)]
        if failed:
            rows.append(course("Nợ", "F", credits=2))
        return rows

    def test_xuat_sac_when_gpa_conduct_and_credits_clear(self):
        out = advising.scholarship_report(self._full(), drl=95)
        sem = out["semesters"][0]
        self.assertEqual(sem["tier"], "Xuất sắc")
        self.assertTrue(sem["eligible"])
        self.assertIn("có thể thay đổi", out["label"])

    def test_kha_when_conduct_misses_gioi(self):
        out = advising.scholarship_report(self._full("B"), drl=70)
        self.assertEqual(out["semesters"][0]["tier"], "Khá")

    def test_fail_or_light_load_blocks_the_tier(self):
        failed = advising.scholarship_report(self._full(failed=True), drl=95)
        self.assertFalse(failed["semesters"][0]["eligible"])
        self.assertTrue(any("không đạt" in reason for reason in failed["semesters"][0]["reasons"]))
        light = advising.scholarship_report([course("Chỉ một môn", "A")], drl=95)
        self.assertFalse(light["semesters"][0]["eligible"])
        self.assertTrue(any("tín chỉ" in reason for reason in light["semesters"][0]["reasons"]))


class WarningTests(unittest.TestCase):
    def test_first_semester_below_0_8_lists_how_to_leave(self):
        out = advising.warning_report([course("Yếu", "F", credits=15, score=3.0)])
        self.assertEqual(out["level"], "canh_bao")
        self.assertTrue(out["semesters"][0]["warning"])
        self.assertTrue(any("0,8" in step or "0.8" in step for step in out["exit_steps"]))
        self.assertIn("50%", " ".join(out["exit_steps"]))

    def test_clean_semester_is_not_a_warning(self):
        out = advising.warning_report([course("Ổn", "B", credits=15)])
        self.assertEqual(out["level"], "khong")
        self.assertFalse(out["semesters"][0]["warning"])


if __name__ == "__main__":
    unittest.main()
