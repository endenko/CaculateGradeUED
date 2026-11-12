# -*- coding: utf-8 -*-
import os
import tempfile
import threading
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

    def test_consumer_survives_fork(self):
        """gunicorn --preload (Render injects this) forks after the thread starts."""
        q = ocr_queue.OcrQueue()

        def runner(path, mode):
            time.sleep(0.05)
            return {"success": True, "data": [path], "engine": mode}

        q.set_runner(runner)
        q.ensure()
        self.assertTrue(q.worker_alive())
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                ticket = q.submit("child-image", "computer")
                deadline = time.time() + 3
                state = "timeout"
                while time.time() < deadline:
                    info = q.status(ticket["id"])
                    state = info["status"]
                    if state in ("done", "error"):
                        break
                    time.sleep(0.02)
                os.write(write_fd, state.encode())
            except Exception as exc:  # noqa: BLE001
                os.write(write_fd, ("exc:" + str(exc)).encode())
            finally:
                os._exit(0)
        os.close(write_fd)
        with os.fdopen(read_fd) as handle:
            state = handle.read()
        os.waitpid(pid, 0)
        self.assertEqual(state, "done")

    def test_parent_thread_that_still_looks_alive_is_replaced(self):
        """After preload+fork, Thread.is_alive() can stay True for a dead parent thread."""
        q = ocr_queue.OcrQueue()

        class Ghost(threading.Thread):
            def is_alive(self):  # noqa: D102
                return True

        q._thread = Ghost(name="ghost")
        q._owner_pid = os.getpid() + 999
        q.set_runner(lambda path, mode: {"success": True, "data": [mode], "engine": "fake"})
        ticket = q.submit("img", "computer")
        deadline = time.time() + 3
        state = "timeout"
        while time.time() < deadline:
            state = q.status(ticket["id"])["status"]
            if state in ("done", "error"):
                break
            time.sleep(0.02)
        self.assertEqual(state, "done")
        self.assertNotIsInstance(q._thread, Ghost)
        self.assertEqual(q._owner_pid, os.getpid())
        self.assertTrue(q.worker_alive())


if __name__ == "__main__":
    unittest.main()
