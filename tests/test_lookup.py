# -*- coding: utf-8 -*-
import unittest

import db
from app import app


class LookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.seed_from_csv()
        db.clear_lookup_cache()
        cls.client = app.test_client()

    def test_lookup_is_accent_insensitive_and_cached(self):
        first = self.client.get("/api/lookup?q=triet hoc")
        self.assertEqual(first.status_code, 200)
        self.assertIn("max-age=120", first.headers.get("Cache-Control", ""))
        rows = first.get_json()
        self.assertTrue(rows)
        hit = rows[0]
        self.assertIn("Triết", hit["ten_mon"])
        self.assertTrue(hit["ma_hp"])
        self.assertGreater(hit["tin_chi"], 0)
        self.assertTrue(hit["khoa"])
        self.assertGreater(hit["program_count"], 0)
        again = self.client.get("/api/lookup?q=triet hoc")
        self.assertEqual(again.get_json()[0]["ten_mon"], hit["ten_mon"])

    def test_short_query_is_empty(self):
        self.assertEqual(self.client.get("/api/lookup?q=a").get_json(), [])


if __name__ == "__main__":
    unittest.main()
