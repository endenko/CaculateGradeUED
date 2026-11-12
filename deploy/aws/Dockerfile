# Light OCR image for a 1 GB EC2 instance. Do not use the repo-root Dockerfile:
# that one installs VietOCR and needs about 1.5 GB.
FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OCR_LIGHT=1 \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    RAPID_LIMIT_SIDE=960 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /tmp/uploads uploads \
    && python seed_db.py

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2", "--timeout", "120", "app:app"]
