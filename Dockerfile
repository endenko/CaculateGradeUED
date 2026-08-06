# 🌸 UED Calculate Grade — Docker image
# OCR engines: Tesseract (computer mode) + PaddleOCR Vietnamese (handwriting mode)
# No API keys needed — everything runs offline inside the container.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    DB_PATH=/app/data/grade.db \
    OCR_HANDWRITING_ENGINE=paddle \
    UPLOAD_FOLDER=/app/uploads

# --- System deps: Tesseract + vie language pack, OpenCV/Paddle shared libs ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-vie \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps (cached layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- App code ---
COPY . .

# --- Build the SQLite DB from seed CSV ---
RUN python seed_db.py

# --- Pre-download PaddleOCR Vietnamese models so the container works offline ---
RUN python -c "from ocr.engines import warmup; warmup()"

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=5)"

# Re-seed SQLite from the mounted CSV at every start (idempotent), then serve.
# Edit data/danh_muc_mon.csv on the host and `docker compose restart` to apply.
CMD ["sh", "-c", "python seed_db.py && exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 300 app:app"]
