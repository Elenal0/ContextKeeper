"""Tests for carry forward and history preservation."""
import pytest
from fastapi import HTTPException

from app.db.models import ActionItem, ItemEventType, ItemStatus, Meeting, MeetingStatus
from app.schemas.items import ActionItemCreate
from app.services.carry_forward import carry_forward_items
from app.services.items import create_item


def test_carry_forward_open_item_preserves_history(db_session):
    m1 = Meeting(title="Meeting 1", status=MeetingStatus.completed)
    m2 = Meeting(title="Meeting 2", status=MeetingStatus.scheduled)
    db_session.add_all([m1, m2])
    db_session.commit()

    item = create_item(
        db_session,
        ActionItemCreate(
            title="Database index tuning",
            source_meeting_id=m1.id,
            current_meeting_id=m1.id,
        ),
    )
    assert item.carry_forward_count == 0
    assert item.current_meeting_id == m1.id

    carried = carry_forward_items(
        db=db_session,
        item_ids=[item.id],
        target_meeting_id=m2.id,
    )
    assert len(carried) == 1
    assert carried[0].current_meeting_id == m2.id
    assert carried[0].carry_forward_count == 1

    # Check append-only history trail
    history = carried[0].history
    assert len(history) >= 2
    assert history[-1].event_type == ItemEventType.carried_forward
    assert history[-1].old_value == str(m1.id)
    assert history[-1].new_value == str(m2.id)


def test_cannot_carry_forward_closed_item(db_session):
    m1 = Meeting(title="Meeting 1", status=MeetingStatus.completed)
    m2 = Meeting(title="Meeting 2", status=MeetingStatus.scheduled)
    db_session.add_all([m1, m2])
    db_session.commit()

    item = create_item(
        db_session,
        ActionItemCreate(
            title="Completed task",
            source_meeting_id=m1.id,
            current_meeting_id=m1.id,
        ),
    )
    item.status = ItemStatus.done
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        carry_forward_items(
            db=db_session,
            item_ids=[item.id],
            target_meeting_id=m2.id,
        )
    assert exc.value.status_code == 400
    assert "Cannot carry forward closed item" in exc.value.detail

