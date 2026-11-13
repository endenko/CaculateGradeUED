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


class OutlookTests(unittest.TestCase):
    def test_gap_and_future_credits_when_nothing_is_open(self):
        from solver import cpa_outlook
        fixed = [{"ten_mon": "Sử", "credits": 20, "points": 3.0, "letter": "B", "lan": 1}]
        out = cpa_outlook(fixed, [], target=3.2)
        self.assertFalse(out["reached"])
        self.assertEqual(out["cpa"], 3.0)
        self.assertEqual(out["credits"], 20)
        self.assertAlmostEqual(out["gap"], 0.2)
        self.assertGreater(out["future_a_credits"], 0)
        self.assertGreater(out["future_bplus_credits"], out["future_a_credits"])
        high = cpa_outlook(fixed, [], target=3.6)
        self.assertGreater(high["future_a_credits"], 0)
        self.assertIsNone(high["future_bplus_credits"])

    def test_already_reached_states_margin_and_room(self):
        from solver import cpa_outlook
        fixed = [{"ten_mon": "Toán", "credits": 30, "points": 4, "letter": "A", "lan": 1}]
        out = cpa_outlook(fixed, [], target=3.6)
        self.assertTrue(out["reached"])
        self.assertAlmostEqual(out["margin"], 0.4)
        self.assertGreater(out["afford_b"], 0)
        self.assertGreater(out["afford_b"], out["afford_c"])

    def test_open_course_plans_or_best_reachable(self):
        from solver import cpa_outlook
        fixed = [{"ten_mon": "Văn", "credits": 20, "points": 3.5, "letter": "B+", "lan": 1}]
        variable = [{"id": "gd", "ten_mon": "Giáo dục thể chất 4", "credits": 1, "bp": 8, "gk": 7, "ck": None}]
        out = cpa_outlook(fixed, variable, target=3.6)
        self.assertTrue(out["has_in_progress"])
        self.assertLessEqual(len(out["plans"]), 5)
        if out["all_a_reaches"]:
            self.assertTrue(out["plans"])
            self.assertGreaterEqual(out["plans"][0]["gpa"], 3.6)
        else:
            self.assertIsNotNone(out["best_reachable"])
            self.assertLess(out["best_reachable"], 3.6)

    def test_retake_note_only_when_second_attempt_exceeds_five_percent(self):
        from solver import cpa_outlook
        small = [{"ten_mon": "A", "credits": 2, "points": 3, "letter": "B", "lan": 2}]
        self.assertIsNone(cpa_outlook(small, [], target=3.2, program_credits=130)["retake_note"])
        heavy = [{"ten_mon": "B", "credits": 10, "points": 3, "letter": "B", "lan": 2}]
        self.assertIn("lần 2", cpa_outlook(heavy, [], target=3.2, program_credits=130)["retake_note"])


if __name__ == "__main__":
    unittest.main()
