"""
ContextKeeper FastAPI Application.

AI-Powered Knowledge & Task Management Platform with Handover Risk Radar.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db.base import Base
from app.db.session import engine
from app.logging_config import configure_logging, get_logger, request_id_var
from app.middleware import AccessLogMiddleware, RequestIDMiddleware
from app.routers import (
    admin,
    ai_router,
    items,
    kb,
    meetings,
    people,
    risk_router,
    views,
)
from app.schemas.common import ErrorDetail, ErrorEnvelope, ErrorResponse

logger = get_logger("app.main")


def _ensure_data_dirs() -> None:
    """Create LOG_DIR and UPLOAD_DIR on the volume if they don't exist."""
    for dir_path in (settings.LOG_DIR, settings.UPLOAD_DIR):
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Don't crash — fall back gracefully; logging will use stdout
            print(f"[WARN] Could not create directory {dir_path}: {e}")


def _check_fts5() -> bool:
    """Return True if the SQLite build supports FTS5."""
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(x)")
        conn.close()
        return True
    except Exception:
        return False


def _run_migrations() -> None:
    """Run Alembic migrations idempotently at startup."""
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("alembic_migrations_applied")
    except Exception as exc:
        # If alembic fails (e.g. first boot, alembic not configured),
        # fall back to create_all so the app still starts.
        logger.warning("alembic_migration_failed_falling_back_to_create_all", error=str(exc))
        Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 0. Production secrets guard ───────────────────────────────────────────
    settings.validate_production_secrets()

    # ── 1. Ensure persistent volume directories exist ─────────────────────────
    _ensure_data_dirs()

    # ── 2. Initialize structured logging ─────────────────────────────────────
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        audit_log_file=settings.AUDIT_LOG_FILE,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT,
    )
    logger.info("app_starting", app_name=settings.APP_NAME, env=settings.APP_ENV)

    # ── 3. FTS5 availability check ────────────────────────────────────────────
    if _check_fts5():
        logger.info("fts5_available")
    else:
        logger.warning(
            "fts5_unavailable",
            fallback="LIKE-based search active — FTS5 not compiled into this SQLite build",
        )

    # ── 4. Run Alembic migrations (idempotent, non-destructive) ──────────────
    _run_migrations()

    logger.info("app_ready", ai_provider=settings.effective_ai_provider())
    yield

    logger.info("app_stopping")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Knowledge & Task Management Platform with Handover Risk Radar",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware Stack (RequestID must wrap everything) ────────────────────────
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Static Files ─────────────────────────────────────────────────────────────
static_dir = Path(__file__).parent / "static"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Exception Handlers (Consistent Error Envelope) ────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = request_id_var.get()
    error_env = ErrorEnvelope(
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        details=[],
        request_id=req_id,
    )
    logger.warning("http_exception", status_code=exc.status_code, detail=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=error_env).model_dump(),
        headers={"X-Request-ID": req_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = request_id_var.get()
    details = [
        ErrorDetail(field=" -> ".join(str(loc) for loc in err["loc"]), message=err["msg"])
        for err in exc.errors()
    ]
    error_env = ErrorEnvelope(
        code="VALIDATION_ERROR",
        message="Invalid request input payload",
        details=details,
        request_id=req_id,
    )
    logger.warning("validation_error", errors=len(details))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(error=error_env).model_dump(),
        headers={"X-Request-ID": req_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request_id_var.get()
    logger.exception("unhandled_server_error", error=str(exc))
    error_env = ErrorEnvelope(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred. Please contact support with this request ID.",
        details=[ErrorDetail(message=str(exc))],
        request_id=req_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(error=error_env).model_dump(),
        headers={"X-Request-ID": req_id},
    )


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["system"])
def health_check():
    """Liveness probe: checks DB connectivity only. No AI calls, stays cheap."""
    db_ok = True
    db_detail = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_detail = f"unhealthy: {e}"

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "database": db_detail,
        "ai_provider": settings.effective_ai_provider(),
    }


# ── Routers ──────────────────────────────────────────────────────────────────
# HTML Web Views
app.include_router(views.router)

# REST APIs
app.include_router(people.router)
app.include_router(meetings.router)
app.include_router(items.router)
app.include_router(kb.router)
app.include_router(ai_router.router)
app.include_router(risk_router.router)
app.include_router(admin.router)
