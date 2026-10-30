"""Admin router — view recent application logs, AI runs, and seed (protected by ADMIN_TOKEN)."""
from __future__ import annotations

import os
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AIRun
from app.db.session import get_db
from app.schemas.ai import AIRunOut

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    token: str | None = Query(None),
) -> bool:
    supplied = x_admin_token or token
    if not supplied or supplied != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")
    return True


@router.get("/logs")
def get_recent_logs(
    limit: int = Query(100, ge=1, le=500),
    _: bool = Depends(verify_admin),
):
    """Tail recent log lines from the rotating JSON application log file."""
    log_path = Path(settings.LOG_FILE)
    if not log_path.exists():
        return {"logs": [], "message": f"Log file {settings.LOG_FILE} does not exist yet."}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        recent = [line.strip() for line in lines[-limit:] if line.strip()]
        return {
            "total_lines_returned": len(recent),
            "file": str(log_path),
            "logs": recent,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


@router.get("/ai-runs", response_model=list[AIRunOut])
def get_ai_runs(
    limit: int = Query(50, ge=1, le=200),
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """Retrieve recent AI runs for traceability and observability."""
    return (
        db.query(AIRun)
        .order_by(AIRun.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/seed", status_code=200)
def trigger_seed(_: bool = Depends(verify_admin)):
    """
    Idempotently seed the database with realistic demo data.
    Safe to call multiple times — will clear and re-seed if data already exists.
    Protected by X-Admin-Token header.
    """
    try:
        from app.seed import seed
        seed()
        return {"status": "ok", "message": "Database seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {e}")
