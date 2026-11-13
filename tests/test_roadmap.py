# -*- coding: utf-8 -*-
import unittest

import db
import roadmap


class RoadmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.seed_from_csv()

    def test_lists_the_68_programs(self):
        programs = roadmap.list_programs()
        self.assertEqual(len(programs), 68)
        names = {item["nganh"] for item in programs}
        self.assertIn("Sư phạm Toán học (khóa 2024)", names)
        self.assertNotIn("Danh sách gốc (repo)", names)
        sample = next(item for item in programs if item["nganh"] == "Sư phạm Toán học (khóa 2024)")
        self.assertGreater(sample["tin_chi"], 0)
        self.assertGreater(sample["so_mon"], 0)

    def test_matches_code_name_and_fuzzy_and_skips_failures(self):
        result = roadmap.build_roadmap("Sư phạm Toán học (khóa 2024)", [
            {"ten_mon": "môn khác", "ma_hp": "21231902", "diem_he_4": "A", "tin_chi": 3},
            {"ten_mon": "Kinh tế chính trị Mác - Lênin", "diem_he_4": "B", "tin_chi": 2},
            {"ten_mon": "Lich su Dang Cong san VN", "diem_he_4": "C", "tin_chi": 2},
            {"ten_mon": "Giáo dục thể chất", "diem_he_4": "F", "tin_chi": 1},
            {"ten_mon": "Giải tích", "diem_he_4": "A", "tin_chi": 4},
            {"ten_mon": "Môn ngoài chương trình", "diem_he_4": "A", "tin_chi": 3},
        ])
        self.assertTrue(result["found"])
        matched = {item["ten_mon"]: item["how"] for item in result["done"]}
        self.assertEqual(matched.get("Triết học Mác - Lênin"), "ma_hp")
        self.assertEqual(matched.get("Kinh tế chính trị Mác - Lênin"), "ten")
        self.assertEqual(matched.get("Lịch sử Đảng Cộng sản Việt Nam"), "fuzzy")
        self.assertNotIn("Giáo dục thể chất", matched)
        self.assertNotIn("Giải tích hàm", matched)
        self.assertIn("Giải tích", result["extra"])
        self.assertIn("Môn ngoài chương trình", result["extra"])
        self.assertGreater(result["percent"], 0)
        self.assertLess(result["percent"], 100)
        self.assertGreater(result["missing_count"], 0)

    def test_unknown_program(self):
        result = roadmap.build_roadmap("Không có ngành này", [])
        self.assertFalse(result["found"])

    def test_pass_only_counts_and_empty_does_not(self):
        self.assertTrue(roadmap.course_passed({"pass_only": True}))
        self.assertTrue(roadmap.course_passed({"diem_10": 4}))
        self.assertFalse(roadmap.course_passed({"diem_10": 3.9}))
        self.assertFalse(roadmap.course_passed({"diem_he_4": "F"}))
        self.assertFalse(roadmap.course_passed({"ten_mon": "Trống"}))

    def test_bang2_letter_counts_and_open_course_is_in_progress(self):
        result = roadmap.build_roadmap("Sư phạm Toán học (khóa 2024)", [
            {"ten_mon": "Triết học Mác - Lênin", "letter": "A", "tin_chi": 3, "source": "bang2"},
            {"ten_mon": "Kinh tế chính trị Mác - Lênin", "in_progress": True, "source": "bang2"},
        ])
        done = {item["ten_mon"] for item in result["done"]}
        self.assertIn("Triết học Mác - Lênin", done)
        studying = [item for item in result.get("semesters", []) if False]
        flat = result["done"] + result["missing"]
        # In-progress row is not a pass, so it must not be listed as đã đạt.
        self.assertNotIn("Kinh tế chính trị Mác - Lênin", done)
        names = {item["ten_mon"]: item["status"] for item in (result.get("semesters") and [])}
        # Status lives on semester rows when a plan exists, otherwise only dat/thieu split.
        if result.get("has_plan"):
            status = {}
            for sem in result["semesters"]:
                for row in sem["bat_buoc"] + sem["tu_chon"]:
                    status[row["ten_mon"]] = row["status"]
            self.assertEqual(status.get("Kinh tế chính trị Mác - Lênin"), "dang_hoc")
        else:
            self.assertTrue(roadmap.course_in_progress({"ten_mon": "Kinh tế chính trị Mác - Lênin", "in_progress": True, "source": "bang2"}))


if __name__ == "__main__":
    unittest.main()
