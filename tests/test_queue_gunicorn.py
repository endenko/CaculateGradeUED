# -*- coding: utf-8 -*-
"""Submit several images at once to a gunicorn worker started the way Render does.

Render sets GUNICORN_CMD_ARGS=--preload, which imports the app in the master and
then forks. This test fails if the OCR consumer does not come back in the child.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8871


def _rss_kb(pid):
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    rss = hwm = None
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            rss = int(line.split()[1])
        elif line.startswith("VmHWM:"):
            hwm = int(line.split()[1])
    return rss, hwm


class GunicornQueueTests(unittest.TestCase):
    def test_preload_workers_finish_concurrent_images(self):
        env = os.environ.copy()
        env.update({
            "OCR_LIGHT": "1",
            "OMP_NUM_THREADS": "1",
            "MALLOC_ARENA_MAX": "2",
            "RAPID_LIMIT_SIDE": "960",
            # What Render injects on top of render.yaml's start command.
            "GUNICORN_CMD_ARGS": "--preload --access-logfile -",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        log = tempfile.NamedTemporaryFile(prefix="gunicorn-ocr-", suffix=".log", delete=False)
        log.close()
        cmd = [
            sys.executable, "-m", "gunicorn",
            "--bind", f"127.0.0.1:{PORT}",
            "--workers", "1",
            "--threads", "2",
            "--timeout", "120",
            "app:app",
        ]
        log_handle = open(log.name, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=ROOT, env=env,
            stdout=log_handle, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            self._wait_health()
            paths = self._images(4)
            started = time.time()
            tickets = self._submit_all(paths)
            self.assertEqual(len(tickets), 4)
            infos = self._wait_all(tickets, timeout=60)
            wall = time.time() - started
            for info in infos:
                self.assertEqual(info["status"], "done", info)
                self.assertTrue(info["result"]["success"])
            durations = [info["duration_seconds"] for info in infos]
            self.assertTrue(all(d and d > 0 for d in durations))
            worker_pid = self._worker_pid(proc.pid)
            rss, hwm = _rss_kb(worker_pid)
            # Free tier is 512 MB. Peak RSS of the worker must stay under that.
            self.assertIsNotNone(hwm)
            self.assertLess(hwm, 512 * 1024, f"peak RSS {hwm} KiB")
            waits = []
            for ticket, info in zip(tickets, infos):
                waits.append({
                    "position": ticket.get("position"),
                    "queue_wait_seconds": round(info["_done_at"] - ticket["_sent_at"], 3),
                    "ocr_seconds": info["duration_seconds"],
                })
            report = {
                "wall_seconds": round(wall, 3),
                "per_image_seconds": durations,
                "avg_seconds": infos[-1]["avg_seconds"],
                "waits": waits,
                "rss_kib": rss,
                "hwm_kib": hwm,
                "worker_pid": worker_pid,
            }
            print("OCR_LOAD", json.dumps(report))
        finally:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            log_handle.close()

    def _wait_health(self):
        deadline = time.time() + 20
        last = ""
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as res:
                    body = json.load(res)
                if body.get("success") and body.get("queue_worker") is True:
                    return
                last = str(body)
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
            time.sleep(0.2)
        self.fail("gunicorn did not become healthy: " + last)

    def _images(self, n):
        from PIL import Image, ImageDraw
        paths = []
        for i in range(n):
            # ~phone photo after the client downscale (max side 2000)
            im = Image.new("RGB", (1600, 900), "white")
            draw = ImageDraw.Draw(im)
            for row in range(8):
                draw.text((40, 60 + row * 90), f"Mon hoc so {i + 1}.{row}    3    8.{row}    A", fill="black")
            path = os.path.join(tempfile.gettempdir(), f"ocr-queue-{PORT}-{i}.png")
            im.save(path)
            paths.append(path)
        return paths

    def _submit_all(self, paths):
        import threading
        out = [None] * len(paths)

        def one(i):
            sent = time.time()
            result = subprocess.run(
                ["curl", "-sS", "--no-keepalive", "-F", f"file_anh=@{paths[i]}", "-F", "mode=computer",
                 f"http://127.0.0.1:{PORT}/api/ocr/jobs"],
                capture_output=True, text=True, check=True,
            )
            ticket = json.loads(result.stdout)
            ticket["_sent_at"] = sent
            out[i] = ticket

        threads = [threading.Thread(target=one, args=(i,)) for i in range(len(paths))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for ticket in out:
            self.assertTrue(ticket["accepted"], ticket)
        return out

    def _wait_all(self, tickets, timeout):
        deadline = time.time() + timeout
        pending = {t["id"] for t in tickets}
        done = {}
        while pending and time.time() < deadline:
            for job_id in list(pending):
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ocr/jobs/{job_id}", timeout=5) as res:
                    info = json.load(res)
                if info["status"] in ("done", "error"):
                    info["_done_at"] = time.time()
                    done[job_id] = info
                    pending.discard(job_id)
            time.sleep(0.05)
        self.assertFalse(pending, "jobs still pending: " + ", ".join(pending))
        return [done[t["id"]] for t in tickets]

    def _worker_pid(self, master_pid):
        text = subprocess.check_output(["ps", "-ax", "-o", "pid=,ppid="], text=True)
        children = []
        for line in text.splitlines():
            pid_s, ppid_s = line.split()
            if int(ppid_s) == master_pid:
                children.append(int(pid_s))
        self.assertTrue(children, f"no child of {master_pid}")
        return children[0]


if __name__ == "__main__":
    unittest.main()
