# -*- coding: utf-8 -*-
import io
import unittest
import zipfile

from app import app


class StudioRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_programs_and_roadmap_round_trip(self):
        programs = self.client.get("/api/programs").get_json()
        self.assertEqual(len(programs), 68)
        response = self.client.post("/api/roadmap", json={
            "nganh": "Sư phạm Toán học (khóa 2024)",
            "courses": [{"ten_mon": "Triết học Mác - Lênin", "diem_he_4": "A", "tin_chi": 3}],
        })
        body = response.get_json()
        self.assertTrue(body["found"])
        self.assertEqual(body["done_count"], 1)
        self.assertGreater(body["remaining_credits"], 0)

    def test_gpa_series_groups_terms(self):
        response = self.client.post("/api/gpa_series", json={"courses": [
            {"ten_mon": "A", "tin_chi": 2, "diem_he_4": "A", "nam_hoc": "2024-2025", "hoc_ky": "1", "lan": 1},
            {"ten_mon": "B", "tin_chi": 2, "diem_he_4": "B", "nam_hoc": "2024-2025", "hoc_ky": "2", "lan": 1},
        ]})
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual([item["hoc_ky"] for item in body["semesters"]], ["1", "2"])
        self.assertEqual(body["semesters"][0]["gpa"], 4.0)
        self.assertIsNotNone(body["semesters"][1]["cumulative_gpa"])

    def test_xlsx_download(self):
        response = self.client.post("/api/export.xlsx", json={
            "bang1": [{"ten_mon": "Giải tích", "tin_chi": 3, "diem_he_4": "A"}],
            "bang2": [],
            "summary": {"cpa": "4.00"},
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response.content_type)
        with zipfile.ZipFile(io.BytesIO(response.data)) as book:
            sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("Giải tích", sheet)

    def test_pwa_files(self):
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.get_json()["display"], "standalone")
        self.assertEqual(self.client.get("/sw.js").status_code, 200)
        offline = self.client.get("/offline.html")
        self.assertEqual(offline.status_code, 200)
        self.assertIn("Không có mạng".encode(), offline.data)


if __name__ == "__main__":
    unittest.main()
