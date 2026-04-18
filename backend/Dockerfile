FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch (smaller image than default pip torch).
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/requirements-docker.txt

COPY app /app/app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Render sets PORT; local Docker Compose defaults to 8000.
CMD ["/bin/sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 120"]
