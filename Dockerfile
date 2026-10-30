# ── Build stage: compile wheels so the final image is small ──────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install only the C toolchain needed to build wheels, then discard it
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy pre-built wheels from builder
COPY --from=builder /install /usr/local

# Copy only the application source (tests, docs, uploads, DB files excluded via .dockerignore)
COPY alembic.ini .
COPY migrations/ migrations/
COPY app/ app/

# Create the volume mount-point directories and make them writable by appuser
# /data will be replaced by the Fly.io persistent volume at runtime
RUN mkdir -p /data/logs /data/uploads \
    && chown -R appuser:appgroup /data

# Runtime configuration (overridden by Fly.io [env] and secrets)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/contextkeeper.db \
    LOG_DIR=/data/logs \
    UPLOAD_DIR=/data/uploads

EXPOSE 8080

# Lightweight healthcheck — hits /healthz (DB ping, no AI calls)
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

USER appuser

# Single worker — SQLite on one volume cannot be shared across processes
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
