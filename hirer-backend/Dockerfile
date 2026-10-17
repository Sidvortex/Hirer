FROM python:3.11-slim

# System packages for OCR: Tesseract reads text from images, Poppler lets pdf2image render PDF pages
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch keeps the image far smaller than the default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Live-server limits (0 = no limit). Local runs without Docker have no limits.
ENV JSONL_ENTRY_LIMIT=1000 \
    PDF_COUNT_LIMIT=50 \
    PDF_SIZE_LIMIT_MB=50

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
