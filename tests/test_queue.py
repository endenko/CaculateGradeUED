# -*- coding: utf-8 -*-
import os
import tempfile
import time
import unittest

import ocr_queue


class QueueTests(unittest.TestCase):
    def test_one_at_a_time_and_eta(self):
        q = ocr_queue.OcrQueue()
        started = []

        def runner(path, mode):
            started.append(time.time())
            time.sleep(0.15)
            return {"success": True, "data": [], "engine": mode}

        q.set_runner(runner)
        a = tempfile.NamedTemporaryFile(delete=False)
        b = tempfile.NamedTemporaryFile(delete=False)
        a.close(); b.close()
        try:
            t1 = q.submit(a.name, "computer")
            t2 = q.submit(b.name, "computer")
            self.assertTrue(t1["accepted"] and t2["accepted"])
            self.assertGreaterEqual(t2["ahead"], 1)
            self.assertGreater(t2["eta_seconds"], 0)
            deadline = time.time() + 3
            while time.time() < deadline:
                if q.status(t1["id"])["status"] == "done" and q.status(t2["id"])["status"] == "done":
                    break
                time.sleep(0.05)
            self.assertEqual(q.status(t1["id"])["status"], "done")
            self.assertEqual(q.status(t2["id"])["status"], "done")
            self.assertGreaterEqual(started[1] - started[0], 0.1)
        finally:
            os.unlink(a.name)
            os.unlink(b.name)


if __name__ == "__main__":
    unittest.main()
