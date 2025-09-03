FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app ./app

# Set timezone to Asia/Singapore
ENV TZ=Asia/Singapore

# Healthcheck (simple)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fs http://localhost:8080/health || exit 1
