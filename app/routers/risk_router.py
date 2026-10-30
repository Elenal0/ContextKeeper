"""Risk Radar router — Context-Loss Risk scores across open action items."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ai import ItemRisk
from app.services.nudges import get_risk_radar

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("", response_model=list[ItemRisk])
def get_radar(db: Session = Depends(get_db)):
    """Retrieve all open items scored and sorted by Context-Loss Risk Score (0-100)."""
    return get_risk_radar(db)

