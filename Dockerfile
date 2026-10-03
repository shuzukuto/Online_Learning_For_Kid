# ─────────────────────────────────────────────
# EduQuest Pro — Dockerfile
# Base: python:3.12-slim (Linux, chạy trong Docker Desktop Windows)
# ─────────────────────────────────────────────

FROM python:3.12-slim

# ── Metadata ──────────────────────────────────
LABEL maintainer="EduQuest Pro"
LABEL description="Thu thập & Quản lý Ngân hàng Câu hỏi Thi Trực tuyến"

# ── System dependencies ───────────────────────
# Cần cho: Pillow (libpng, libjpeg), Playwright (Chromium), onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Pillow / image processing
    libpng-dev libjpeg-dev libwebp-dev \
    # Playwright / Chromium headless browser
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 \
    libx11-6 libxcb1 libxext6 libx11-xcb1 libxss1 \
    # Utilities
    curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────
# Copy requirements trước để tận dụng Docker layer cache
# (Nếu requirements.txt không đổi, bước này bị cache → build nhanh hơn)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Install Playwright browser (Chromium) ─────
# Cần cho tính năng Auto-Hunter scraping headless
RUN playwright install chromium --with-deps 2>/dev/null || \
    echo "[INFO] Playwright browser install skipped (non-critical)"

# ── Copy source code ──────────────────────────
COPY backend/  ./backend/
COPY frontend/ ./frontend/

# ── Data directory (sẽ được mount từ ngoài) ───
# Tạo thư mục mặc định phòng khi chưa mount volume
RUN mkdir -p /app/data/media /app/data/models

# ── Port ──────────────────────────────────────
EXPOSE 8000

# ── Health check ──────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/stats/count || exit 1

# ── Startup command ───────────────────────────
CMD ["uvicorn", "backend.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
