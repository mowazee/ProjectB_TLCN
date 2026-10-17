# Một image cho API, worker và beat (ADR-ASYNC-001: dùng chung codebase).
# Mặc định chạy API; compose ghi đè command cho worker/beat.
#   docker build -t docso-backend .                       # API + worker OCR in
#   docker build --build-arg WITH_OCR=0 -t docso-api .    # image nhẹ không có PaddleOCR (chỉ API/beat)
#   docker build --build-arg WITH_HW=1 -t docso-backend-hw .  # + VietOCR (PyTorch CPU) cho worker chữ viết tay P2-03
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt requirements-ocr.txt requirements-hw.txt constraints.txt ./
ARG WITH_OCR=1
ARG WITH_HW=0
RUN pip install -r requirements.txt -c constraints.txt \
    && if [ "$WITH_OCR" = "1" ]; then pip install -r requirements-ocr.txt -c constraints.txt; fi
# VietOCR: PyTorch bản CPU (bản mặc định trên Linux kèm CUDA, vài GB); vietocr --no-deps (xem requirements-hw.txt)
RUN if [ "$WITH_HW" = "1" ]; then \
      pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-hw.txt -c constraints.txt \
      && pip install vietocr==0.3.13 --no-deps; \
    fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# .paddlex phải có sẵn và thuộc user app: volume "models" mount vào đây được khởi tạo theo quyền trong image
# (nếu thư mục không tồn tại, Docker tạo với owner root -> worker không tải được model OCR).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/storage /home/app/.paddlex \
    && chown -R app /data /app /home/app/.paddlex
USER app
ENV STORAGE_ROOT=/data/storage
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
