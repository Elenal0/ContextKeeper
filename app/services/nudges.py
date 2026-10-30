"""
Nudges & Risk Radar service — queries DB, computes risk scores, drafts smart nudges.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.tasks.nudge import generate_nudge
from app.db.models import ActionItem, ItemEventType, ItemHistory, ItemStatus, KBLink, Meeting, Participant, Person
from app.logging_config import get_audit_logger, get_logger
from app.schemas.ai import ItemRisk, NudgeResponse, RiskSignal
from app.services.risk import compute_item_risk

logger = get_logger("services.nudges")
audit = get_audit_logger()


def get_risk_radar(db: Session) -> list[ItemRisk]:
    """
    Compute context-loss risk scores for all open action items, sorted by risk descending.
    """
    now = datetime.now(timezone.utc)
    open_items = (
        db.query(ActionItem)
        .filter(ActionItem.status.in_([ItemStatus.open, ItemStatus.in_progress, ItemStatus.blocked]))
        .all()
    )

    results: list[ItemRisk] = []

    for item in open_items:
        owner = db.query(Person).filter(Person.id == item.owner_id).first() if item.owner_id else None
        owner_name = owner.name if owner else "Unassigned"

        # Source meeting participants
        source_participants = []
        if item.source_meeting_id:
            source_participants = (
                db.query(Participant)
                .filter(Participant.meeting_id == item.source_meeting_id)
                .all()
            )

        # KB link count
        kb_count = (
            db.query(KBLink)
            .filter(KBLink.item_id == item.id)
            .count()
        )

        # Days since last updated
        updated = item.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        days_stale = max(0, int((now - updated).total_seconds() / 86400.0))

        # Check for unnoted reassignment
        has_unnoted_reassign = False
        reassign_events = (
            db.query(ItemHistory)
            .filter(
                ItemHistory.item_id == item.id,
                ItemHistory.event_type == ItemEventType.reassigned,
            )
            .all()
        )
        for rev in reassign_events:
            if not rev.note or rev.note.strip() == "":
                has_unnoted_reassign = True
                break

        score, raw_signals = compute_item_risk(
            item=item,
            owner=owner,
            source_participants=source_participants,
            has_kb_link=kb_count > 0,
            days_since_updated=days_stale,
            has_unnoted_reassignment=has_unnoted_reassign,
            now=now,
        )

        # Format fired signals
        signals = [RiskSignal(signal=s["signal"], description=s["description"]) for s in raw_signals]

        # Plain-English summary of top risks
        why_bullets = [s.description for s in signals[:3]]
        ai_why = "; ".join(why_bullets) if why_bullets else "No significant risks detected."

        results.append(
            ItemRisk(
                item_id=item.id,
                item_title=item.title,
                owner_name=owner_name,
                risk_score=score,
                signals=signals,
                ai_why=ai_why,
                ai_run_id="",
            )
        )

    # Sort descending by risk score
    results.sort(key=lambda r: r.risk_score, reverse=True)
    return results


async def generate_nudge_for_item(
    db: Session,
    item_id: int,
    tone: str = "friendly",
    actor_id: int | None = None,
) -> NudgeResponse:
    item = db.query(ActionItem).filter(ActionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Action item {item_id} not found")

    owner = db.query(Person).filter(Person.id == item.owner_id).first() if item.owner_id else None
    owner_name = owner.name if owner else "there"

    # Calculate days overdue
    overdue_days = 0
    if item.due_date:
        now = datetime.now(timezone.utc)
        due = item.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        diff = (now - due).total_seconds() / 86400.0
        if diff > 0:
            overdue_days = int(diff)

    due_str = item.due_date.strftime("%b %d, %Y") if item.due_date else "no fixed date"

    nudge_res = await generate_nudge(
        item_title=item.title,
        owner_name=owner_name,
        due_date=due_str,
        tone=tone,
        overdue_days=overdue_days,
        db=db,
    )

    audit.info(
        "nudge.generated",
        item_id=item.id,
        owner_name=owner_name,
        tone=tone,
        actor_id=actor_id,
        ai_run_id=nudge_res.ai_run_id,
    )

    return nudge_res

