# Hirer backend. Build from the repo root so the shared hirer_core package is included:
#   docker build -t hirer-backend .
#   docker run -p 8000:8000 hirer-backend
FROM python:3.11-slim

# Tesseract reads text from images; Poppler lets pdf2image render scanned PDF pages
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch keeps the image far smaller than the default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY hirer-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model at build time so the first semantic run doesn't wait for it
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    || echo "model download skipped; it will download on first use"

COPY hirer_core ./hirer_core
COPY hirer-backend ./hirer-backend

# Live-server limits (0 = no limit). Local runs without Docker have no limits.
ENV JSONL_ENTRY_LIMIT=1000 \
    PDF_COUNT_LIMIT=50 \
    PDF_SIZE_LIMIT_MB=50

WORKDIR /app/hirer-backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
