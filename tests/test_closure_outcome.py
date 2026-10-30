"""Tests for Action Item closure requiring outcome and resolution type."""
import pytest
from fastapi import HTTPException

from app.db.models import ActionItem, ItemEventType, ItemStatus, ResolutionType
from app.schemas.items import ActionItemCreate
from app.services.items import close_item, create_item


def test_close_item_success_with_outcome(db_session):
    item = create_item(db_session, ActionItemCreate(title="Investigate cache hit ratio"))
    assert item.status == ItemStatus.open

    closed = close_item(
        db=db_session,
        item_id=item.id,
        outcome="Configured Redis cache; hit ratio improved from 45% to 88%.",
        resolution_type=ResolutionType.completed,
    )
    assert closed.status == ItemStatus.done
    assert closed.outcome != ""
    assert closed.resolution_type == ResolutionType.completed
    assert closed.closed_at is not None

    # History event recorded
    history = closed.history
    assert any(h.event_type == ItemEventType.outcome_recorded for h in history)


def test_close_item_rejected_without_outcome(db_session):
    item = create_item(db_session, ActionItemCreate(title="Investigate cache hit ratio"))

    with pytest.raises(HTTPException) as exc:
        close_item(
            db=db_session,
            item_id=item.id,
            outcome="   ",  # empty outcome rejected!
            resolution_type=ResolutionType.completed,
        )
    assert exc.value.status_code == 400
    assert "outcome must be provided" in exc.value.detail.lower()

