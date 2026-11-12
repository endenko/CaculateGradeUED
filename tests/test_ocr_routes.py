# -*- coding: utf-8 -*-
"""OCR HTTP entry points share one queue and one rate limit."""
import io
import time
import unittest

import ocr_queue
from app import app, limiter


class OcrRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        limiter.reset()
        self._previous = ocr_queue.queue._runner
        self.calls = []

        def fake(path, mode):
            self.calls.append((path, mode))
            return {"success": True, "data": [{"ten_mon": "Java"}], "engine": "fake"}

        ocr_queue.queue.set_runner(fake)
        deadline = time.time() + 2
        while time.time() < deadline:
            with ocr_queue.queue._cv:
                busy = any(job["status"] in ("queued", "running") for job in ocr_queue.queue._jobs.values())
            if not busy:
                break
            time.sleep(0.02)
        self.calls.clear()

    def tearDown(self):
        ocr_queue.queue.set_runner(self._previous)
        limiter.reset()

    def _post(self, url):
        return self.client.post(url, data={
            "mode": "computer",
            "file_anh": (io.BytesIO(b"not-a-real-image"), "scan.jpg"),
        }, content_type="multipart/form-data")

    def test_process_ocr_waits_on_the_same_queue(self):
        response = self._post("/api/process_ocr")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["engine"], "fake")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(ocr_queue.queue.worker_alive())

    def test_process_ocr_shares_the_job_rate_limit(self):
        statuses = [self._post("/api/ocr/jobs").status_code for _ in range(5)]
        self.assertEqual(statuses, [200, 200, 200, 200, 200])
        blocked = self._post("/api/process_ocr")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("quá nhanh", blocked.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
