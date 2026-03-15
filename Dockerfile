# ════════════════════════════════════════════════════════
# Larry — LIG Parts Intelligence
# Multi-stage build: keeps the final image lean
# ════════════════════════════════════════════════════════

# ── Stage 1: build deps ──────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile PDF/image libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY requirements.txt .

# Create data directories (will be overridden by volume in prod)
RUN mkdir -p ./app/data/pdfs \
              ./app/data/guides \
              ./app/data/part_images

# Non-root user for security
RUN addgroup --system larry && adduser --system --ingroup larry larry
RUN chown -R larry:larry /app
USER larry

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
