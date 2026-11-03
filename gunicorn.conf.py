# -*- coding: utf-8 -*-
"""Gunicorn picks this file up automatically from the working directory.

Render injects ``GUNICORN_CMD_ARGS=--preload`` (not shown in the dashboard).
Preload imports the app in the master, then forks the worker, which drops the
OCR consumer thread. ``post_fork`` starts that thread again inside the worker
that actually serves requests. Command-line ``--workers`` / ``--bind`` / ``--threads``
still win over anything set here.
"""


def post_fork(server, worker):
    try:
        import ocr_queue
        ocr_queue.queue.ensure()
        server.log.info("OCR queue consumer started in worker pid=%s", worker.pid)
    except Exception:
        server.log.exception("OCR queue consumer failed to start")
