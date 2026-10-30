# ── Build stage ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.11-slim

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY --from=builder /install /usr/local

COPY alembic.ini .
COPY migrations/ migrations/
COPY app/ app/

# Writable data directories for the database, logs and uploads
RUN mkdir -p /data/logs /data/uploads /app/app/static \
    && chown -R appuser:appgroup /data /app/app/static

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/contextkeeper.db \
    LOG_DIR=/data/logs \
    UPLOAD_DIR=/data/uploads

EXPOSE 8080

# Health check follows whatever port the platform provides
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/healthz' % os.environ.get('PORT','8080'))"

USER appuser

# Seed (skips if data exists), then start one worker on the platform's port
CMD ["sh", "-c", "python -m app.seed; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]