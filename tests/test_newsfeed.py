# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

import newsfeed


class NewsTests(unittest.TestCase):
    def test_categories_priority(self):
        self.assertEqual(newsfeed.categorize("Thông báo học bổng khuyến khích")[0], "hoc_bong")
        self.assertEqual(newsfeed.categorize("Đánh giá năng lực tiếng Anh chuẩn đầu ra đợt 25/10/2026")[0], "tieng_anh")
        self.assertEqual(newsfeed.categorize("Tuyển sinh thạc sĩ đợt 2")[0], "thac_si")
        self.assertEqual(newsfeed.categorize("Kế hoạch học kỳ 1 đăng ký học phần")[0], "hoc_tap")
        self.assertEqual(newsfeed.categorize("Hội thảo giáo dục trực tuyến")[0], "khac")

    def test_skips_empty_title_and_loose_dates(self):
        board = newsfeed.build_board([
            {"id": 1, "date": "2026-11-01", "link": "https://ued.udn.vn/a", "title": {"rendered": ""},
             "content": {"rendered": "Hạn đăng ký 01/11/2026"}},
            {"id": 2, "date": "2026-11-02", "link": "https://ued.udn.vn/b",
             "title": {"rendered": "Lịch thi tiếng Anh"},
             "content": {"rendered": "Năm 2019 nhà trường tổ chức. Hạn đăng ký 10/11/2026. Đợt thi ngày 25/11/2026."}},
        ])
        self.assertEqual(len(board["posts"]), 1)
        dates = {e["date"] for e in board["calendar"]}
        self.assertIn("2026-11-10", dates)
        self.assertIn("2026-11-25", dates)
        self.assertNotIn("2019-01-01", dates)

    def test_extract_exam_date(self):
        text = (
            "Thông báo về việc tổ chức đánh giá năng lực tiếng Anh chuẩn đầu ra. "
            "Đợt thi ngày 25/10/2026. Hạn đăng ký đến ngày 10/10/2026."
        )
        events = newsfeed.extract_dates(text, "Thi tiếng Anh", "https://ued.udn.vn/x")
        dates = {e["date"]: e["kind"] for e in events}
        self.assertEqual(dates["2026-10-25"], "han")
        self.assertEqual(dates["2026-10-10"], "han")

    def test_cache_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.json")
            old_path, old_ttl = newsfeed.CACHE_PATH, newsfeed.TTL_SECONDS
            newsfeed.CACHE_PATH = path
            newsfeed.TTL_SECONDS = 1000
            try:
                sample = [{
                    "id": 1,
                    "date": "2026-09-30T08:00:00",
                    "link": "https://ued.udn.vn/2026/09/30/thong-bao/",
                    "title": {"rendered": "Thông báo tiếng Anh"},
                    "content": {"rendered": "<p>Hạn đăng ký 10/10/2026. Thi ngày 25/10/2026.</p>"},
                }]
                first = newsfeed.get_board(now=1_000, fetcher=lambda: sample)
                self.assertEqual(first["cache"], "miss")
                self.assertEqual(first["posts"][0]["category"], "tieng_anh")
                self.assertTrue(any(e["date"] == "2026-10-25" for e in first["calendar"]))
                second = newsfeed.get_board(now=1_100, fetcher=lambda: (_ for _ in ()).throw(RuntimeError("no")))
                self.assertEqual(second["cache"], "fresh")
                stale = newsfeed.get_board(now=5_000, fetcher=lambda: (_ for _ in ()).throw(RuntimeError("down")))
                self.assertEqual(stale["cache"], "stale")
                self.assertTrue(stale["posts"])
            finally:
                newsfeed.CACHE_PATH = old_path
                newsfeed.TTL_SECONDS = old_ttl


if __name__ == "__main__":
    unittest.main()
