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
        self.assertEqual(
            result["done_credits"] + result["remaining_credits"],
            result["required_credits"],
        )
        self.assertGreater(result["percent"], 0)
        self.assertLess(result["percent"], 100)
        self.assertEqual(result["missing_count"] + result["done_count"], result["required_count"])

    def test_unknown_program(self):
        result = roadmap.build_roadmap("Không có ngành này", [])
        self.assertFalse(result["found"])

    def test_pass_only_counts_and_empty_does_not(self):
        self.assertTrue(roadmap.course_passed({"pass_only": True}))
        self.assertTrue(roadmap.course_passed({"diem_10": 4}))
        self.assertFalse(roadmap.course_passed({"diem_10": 3.9}))
        self.assertFalse(roadmap.course_passed({"diem_he_4": "F"}))
        self.assertFalse(roadmap.course_passed({"ten_mon": "Trống"}))


if __name__ == "__main__":
    unittest.main()
