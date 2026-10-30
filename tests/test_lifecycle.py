"""Tests for Meeting & Handover lifecycle state machine."""
import pytest
from fastapi import HTTPException
from app.db.models import Meeting, MeetingStatus
from app.services.meetings import create_meeting, transition_meeting, update_meeting
from app.schemas.meetings import MeetingCreate, MeetingUpdate


def test_valid_meeting_lifecycle_chain(db_session):
    # draft -> scheduled -> in_progress -> completed -> archived
    m = create_meeting(db_session, MeetingCreate(title="Sprint Sync"))
    assert m.status == MeetingStatus.draft

    m = transition_meeting(db_session, m.id, MeetingStatus.scheduled)
    assert m.status == MeetingStatus.scheduled

    m = transition_meeting(db_session, m.id, MeetingStatus.in_progress)
    assert m.status == MeetingStatus.in_progress

    m = transition_meeting(db_session, m.id, MeetingStatus.completed)
    assert m.status == MeetingStatus.completed

    m = transition_meeting(db_session, m.id, MeetingStatus.archived)
    assert m.status == MeetingStatus.archived


def test_invalid_lifecycle_transition_rejected(db_session):
    m = create_meeting(db_session, MeetingCreate(title="Sprint Sync"))
    assert m.status == MeetingStatus.draft

    # Cannot jump directly from draft to completed
    with pytest.raises(HTTPException) as exc:
        transition_meeting(db_session, m.id, MeetingStatus.completed)
    assert exc.value.status_code == 422
    assert "Cannot transition" in exc.value.detail


def test_cannot_edit_archived_meeting(db_session):
    m = create_meeting(db_session, MeetingCreate(title="Old Sprint"))
    transition_meeting(db_session, m.id, MeetingStatus.scheduled)
    transition_meeting(db_session, m.id, MeetingStatus.in_progress)
    transition_meeting(db_session, m.id, MeetingStatus.completed)
    transition_meeting(db_session, m.id, MeetingStatus.archived)

    with pytest.raises(HTTPException) as exc:
        update_meeting(db_session, m.id, MeetingUpdate(title="New Title", version=m.version))
    assert exc.value.status_code == 409
    assert "Cannot update an archived meeting" in exc.value.detail
