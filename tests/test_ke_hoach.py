# -*- coding: utf-8 -*-
import unittest

from ke_hoach import parse_plan


def word(text, x, y):
    return {"t": text, "x": x, "y": y}


class PlanParseTests(unittest.TestCase):
    def test_semester_band_and_elective_heading(self):
        page = [
            word("Học kỳ", 100, 50),
            word("21231902", 220, 80),
            word("Học phần tự chọn", 300, 110),
            word("31321476", 220, 140),
            word("1", 100, 160),
            word("12", 400, 160),
            word("31331070", 220, 180),
            word("2", 100, 240),
            word("Phải tích lũy tối thiểu 130 tín chỉ", 200, 400),
            word("tự chọn tối thiểu 20", 200, 420),
            word("không tính Giáo dục thể chất và Giáo dục quốc phòng", 200, 440),
        ]
        plan = parse_plan([page])
        by_code = {row["ma_hp"]: row for row in plan["courses"]}
        self.assertEqual(by_code["21231902"]["hoc_ky"], 1)
        self.assertEqual(by_code["21231902"]["loai"], "bat_buoc")
        self.assertEqual(by_code["31321476"]["loai"], "tu_chon")
        self.assertEqual(by_code["31331070"]["hoc_ky"], 1)
        self.assertEqual(by_code["31331070"]["loai"], "bat_buoc")
        self.assertEqual(plan["tin_chi_toi_thieu"], 130)
        self.assertEqual(plan["tu_chon_toi_thieu"], 20)
        self.assertTrue(plan["exclude_pe_qp"])

    def test_page_without_hoc_ky_column_adds_no_semester(self):
        page = [word("TT", 40, 20), word("1", 40, 60), word("21231902", 180, 60)]
        self.assertEqual(parse_plan([page])["courses"], [])


if __name__ == "__main__":
    unittest.main()
