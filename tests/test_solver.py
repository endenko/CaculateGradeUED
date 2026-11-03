# -*- coding: utf-8 -*-
import unittest

from solver import component_score, min_ck, solve


class ComponentTests(unittest.TestCase):
    def test_weighted_sum_rounds_then_letter(self):
        # 8*0.2 + 8*0.3 + 9*0.5 = 8.5 -> A = 4
        out = component_score(8, 8, 9)
        self.assertEqual(out["score10"], 8.5)
        self.assertEqual(out["letter"], "A")
        self.assertEqual(out["points"], 4.0)

    def test_min_ck_for_A(self):
        # 8*0.2 + 8*0.3 = 4.0; cần làm tròn >= 8.5 => CK 8.9
        self.assertEqual(min_ck(8, 8, 8.5), 8.9)


class SolveTests(unittest.TestCase):
    def test_semester_picks_lowest_letter_that_hits_target(self):
        table2 = [{
            "id": "m1", "ten_mon": "Java", "credits": 3,
            "bp": 8, "gk": 8, "ck": None, "points": None,
        }]
        out = solve([], table2, target=3.2, scope="semester")
        self.assertEqual(out["label"], "Khả thi (Dễ/Trung bình)")
        self.assertEqual(out["courses"][0]["letter"], "B+")
        self.assertEqual(out["courses"][0]["min_score10"], 8.0)
        self.assertAlmostEqual(out["courses"][0]["min_ck"], 7.9, places=1)
        self.assertGreaterEqual(out["cpa"], 3.2)

    def test_impossible_when_ck_cannot_reach(self):
        table2 = [{
            "id": "m1", "ten_mon": "Sử", "credits": 3,
            "bp": 0, "gk": 0, "ck": None, "points": None,
        }]
        out = solve([], table2, target=3.6, scope="semester")
        self.assertEqual(out["label"], "Bất khả thi trong kỳ này")
        self.assertTrue(out["courses"][0]["ck_over"])

    def test_overall_suggests_retake_of_highlighted_f(self):
        table1 = [{
            "id": "old", "ten_mon": "Giải tích", "credits": 4,
            "letter": "F", "points": 0, "sim": False,
        }]
        table2 = [{
            "id": "now", "ten_mon": "Java", "credits": 3,
            "bp": 5, "gk": 5, "ck": None, "points": None,
        }]
        out = solve(table1, table2, target=2.5, scope="overall")
        self.assertEqual(out["label"], "Bất khả thi trong kỳ này")
        self.assertTrue(out["retakes"])
        self.assertEqual(out["retakes"][0]["ten_mon"], "Giải tích")
        self.assertEqual(out["retakes"][0]["to_letter"], "A")
        self.assertGreater(out["retakes"][0]["gain_per_credit"], 0)
        self.assertTrue(out["retakes"][0]["feasible_after"])
        self.assertGreaterEqual(out["retakes"][0]["projected_cpa"], 2.5)

    def test_simulation_changes_current_cpa(self):
        table1 = [{
            "id": "old", "ten_mon": "Vật lý", "credits": 3,
            "letter": "D", "points": 1, "sim": True, "sim_letter": "A", "sim_points": 4,
        }]
        plain = solve(table1, [], target=3.6, scope="overall")
        self.assertEqual(plain["current_cpa"], 4.0)

    def test_completed_course_counts_and_easy_label(self):
        table2 = [
            {"id": "done", "ten_mon": "Triết", "credits": 3, "letter": "A", "points": 4, "bp": None, "gk": None, "ck": None},
            {"id": "open", "ten_mon": "Anh", "credits": 2, "bp": 9, "gk": 9, "ck": None, "points": None},
        ]
        out = solve([], table2, target=2.5, scope="semester")
        self.assertEqual(out["label"], "Khả thi (Dễ/Trung bình)")
        self.assertLess(out["courses"][0]["min_ck"], 8.5)


if __name__ == "__main__":
    unittest.main()
