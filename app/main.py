"""
ContextKeeper FastAPI Application.

AI-Powered Knowledge & Task Management Platform with Handover Risk Radar.
"""
from __future__ import annotations

import os
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured logging
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        audit_log_file=settings.AUDIT_LOG_FILE,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT,
    )
    logger.info("app_starting", app_name=settings.APP_NAME, env=settings.APP_ENV)

    # Create tables automatically if SQLite
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_initialized")

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
    """Liveness probe: verifies application process and database connectivity."""
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "app": settings.APP_NAME,
        "database": db_status,
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

