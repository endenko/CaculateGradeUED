# UED Calculate Grade — single-server image (UI + API + PaddleOCR + VietOCR)
# Works on Google Cloud Run (PORT=8080 injected) and Hugging Face Docker Spaces (port 7860).
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OCR_HANDWRITING_ENGINE=vietocr OCR_COMPUTER_ENGINE=auto PADDLE_RUN_MODE=paddle \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
    PADDLE_PDX_CACHE_HOME=/app/.paddlex PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    VIETOCR_WEIGHTS=/app/models/vgg_transformer.pth VIETOCR_CONFIG_FILE=/app/models/vietocr.yml \
    WARMUP=1 DB_PATH=/tmp/grade.db UPLOAD_FOLDER=/tmp/uploads HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir --no-deps vietocr==0.3.13
COPY . .
RUN mkdir -p /app/models && curl -L -o /app/models/vgg_transformer.pth https://vocr.vn/data/vietocr/vgg_transformer.pth \
 && DB_PATH=/app/data/grade.db python seed_db.py \
 && HOME=/root python -c "from ocr import engines; engines._get_hybrid(); print('models ok')" \
 && chmod -R a+rX /app
EXPOSE 7860
CMD ["sh", "-c", "mkdir -p /tmp/uploads && cp /app/data/grade.db /tmp/grade.db && exec gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 2 --timeout 290 app:app"]
