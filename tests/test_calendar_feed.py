# -*- coding: utf-8 -*-
import unittest

from app import app
import calendar_feed


class CalendarFeedTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_feed_has_alarms_and_revoke_hides_it(self):
        schedule = {
            "week_start": "2026-08-17",
            "classes": [{
                "id": "c1", "name": "Java", "day": 2, "start": "07:00", "end": "08:45",
                "room": "A5-207", "weeks": [1, 5], "lecturer": "An",
            }],
            "exams": [{
                "id": "e1", "name": "Java", "at": "2026-12-07T13:30:00",
                "room": "B3-102", "hinh_thuc": "Tự luận",
            }],
        }
        created = self.client.post("/api/calendar/feed", json={"schedule": schedule}).get_json()
        body = self.client.get(f"/cal/{created['token']}.ics").data.decode()
        self.assertIn("BEGIN:VALARM", body)
        self.assertIn("TRIGGER:-PT15M", body)
        self.assertIn("TRIGGER:-P1D", body)
        self.assertIn("TRIGGER:-PT1H", body)
        self.assertEqual(body.count("SUMMARY:Java"), 2)
        self.assertIn("SUMMARY:Thi Java", body)
        self.assertIn("webcal://", created["webcal"])
        self.client.post("/api/calendar/feed/revoke", json={"token": created["token"]})
        self.assertEqual(self.client.get(f"/cal/{created['token']}.ics").status_code, 404)
        self.assertFalse(calendar_feed.oauth_enabled())
        self.assertEqual(self.client.get("/api/calendar/google/status").get_json()["enabled"], False)


if __name__ == "__main__":
    unittest.main()
