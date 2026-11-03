# -*- coding: utf-8 -*-
"""Hàng đợi OCR một việc một lúc.

Render (và `gunicorn --preload`) nạp app trong process master rồi mới fork worker.
Thread tạo lúc import không sống sang process con, mà cờ "đã chạy" thì bị copy theo,
nên ảnh nằm trong hàng đợi mãi. Hàng đợi đăng ký `os.register_at_fork` và tự mở
lại luồng tiêu thụ trong process đang phục vụ request.
"""
from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from collections import OrderedDict

_PRIOR_SECONDS = float(os.environ.get("OCR_AVG_SECONDS", "20"))


class OcrQueue:
    def __init__(self):
        self._jobs = OrderedDict()
        self._avg = _PRIOR_SECONDS
        self._samples = 0
        self._runner = None
        self._thread = None
        self._rebuild_sync()
        if hasattr(os, "register_at_fork"):
            os.register_at_fork(after_in_child=self._after_fork_child)

    def _rebuild_sync(self):
        # Lock mới. Lock thừa kế sau fork có thể kẹt nếu luồng đã chết từng giữ nó.
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._boot_lock = threading.Lock()

    def _after_fork_child(self):
        """Chạy trong process con, trước khi threading kịp reset. Không tạo thread ở đây."""
        self._thread = None
        self._rebuild_sync()
        for job in self._jobs.values():
            if job.get("status") == "running":
                job["status"] = "queued"
                job["started"] = None

    def set_runner(self, fn):
        self._runner = fn
        self.ensure()

    def worker_alive(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def ensure(self):
        """Bật luồng tiêu thụ nếu process này chưa có (sau fork hoặc sau khi luồng chết)."""
        with self._boot_lock:
            thread = self._thread
            if thread is not None and thread.is_alive():
                return
            with self._cv:
                for job in self._jobs.values():
                    if job.get("status") == "running":
                        job["status"] = "queued"
                        job["started"] = None
                self._cv.notify_all()
            self._thread = threading.Thread(target=self._loop, name="ocr-queue", daemon=True)
            self._thread.start()

    def submit(self, path: str, mode: str) -> dict:
        self.ensure()
        job_id = uuid.uuid4().hex
        with self._cv:
            waiting = sum(1 for j in self._jobs.values() if j["status"] in ("queued", "running"))
            if waiting >= 20:
                return {"accepted": False, "error": "Hàng đợi OCR đang đầy (20 ảnh). Thử lại sau ít phút."}
            self._jobs[job_id] = {
                "id": job_id, "status": "queued", "path": path, "mode": mode,
                "enqueued": time.time(), "started": None, "finished": None,
                "result": None, "error": None,
            }
            self._cv.notify()
        return {"accepted": True, **self.status(job_id)}

    def status(self, job_id: str) -> dict:
        # Request trạng thái cũng kéo luồng dậy, phòng khi consumer chết giữa chừng.
        self.ensure()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"found": False}
            ahead = 0
            for jid, other in self._jobs.items():
                if jid == job_id:
                    break
                if other["status"] in ("queued", "running"):
                    ahead += 1
            if job["status"] == "running":
                ahead = 0
                eta = max(1, int(self._avg - (time.time() - (job["started"] or time.time()))))
            elif job["status"] == "queued":
                eta = int(round((ahead + 1) * self._avg))
            else:
                eta = 0
            duration = None
            if job.get("finished") and job.get("started"):
                duration = round(job["finished"] - job["started"], 3)
            return {
                "found": True,
                "id": job_id,
                "status": job["status"],
                "position": ahead + 1 if job["status"] == "queued" else (0 if job["status"] == "running" else None),
                "ahead": ahead,
                "eta_seconds": eta,
                "avg_seconds": round(self._avg, 1),
                "duration_seconds": duration,
                "result": job["result"],
                "error": job["error"],
                "worker_alive": self.worker_alive(),
                "formula": "ETA = số việc phía trước (kể cả việc đang chạy) × thời gian OCR trung bình",
            }

    def _loop(self):
        while True:
            try:
                self._run_one()
            except Exception:
                traceback.print_exc()
                time.sleep(0.3)

    def _run_one(self):
        with self._cv:
            job_id = next((jid for jid, j in self._jobs.items() if j["status"] == "queued"), None)
            while job_id is None:
                self._cv.wait(timeout=2)
                job_id = next((jid for jid, j in self._jobs.items() if j["status"] == "queued"), None)
            job = self._jobs[job_id]
            job["status"] = "running"
            job["started"] = time.time()
            path, mode = job["path"], job["mode"]
            runner = self._runner
        try:
            result = runner(path, mode) if runner else {"success": False, "error": "OCR chưa sẵn sàng"}
            if isinstance(result, dict) and result.get("success"):
                error = None
            elif isinstance(result, dict):
                error = result.get("error") or "OCR lỗi"
            else:
                result = None
                error = "OCR lỗi"
        except Exception as exc:  # noqa: BLE001
            result = None
            error = str(exc)
        finished = time.time()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "done" if error is None else "error"
            job["finished"] = finished
            job["result"] = result
            job["error"] = error
            if error is None and job["started"]:
                dur = max(0.05, finished - job["started"])
                self._samples += 1
                self._avg = dur if self._samples == 1 else (0.5 * self._avg + 0.5 * dur)
        _trim_memory()


def _trim_memory():
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


queue = OcrQueue()
