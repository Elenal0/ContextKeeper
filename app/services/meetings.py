"""Meetings service — CRUD, lifecycle transitions, participants."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import (
    ActionItem,
    ItemStatus,
    Meeting,
    MeetingStatus,
    Participant,
    RSVP,
    VALID_TRANSITIONS,
)
from app.schemas.meetings import MeetingCreate, MeetingUpdate, ParticipantCreate

logger = structlog.get_logger("services.meetings")


def list_meetings(
    db: Session,
    type_filter: str | None = None,
    status_filter: str | None = None,
    participant_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Meeting]:
    q = db.query(Meeting)
    if type_filter:
        q = q.filter(Meeting.meeting_type == type_filter)
    if status_filter:
        q = q.filter(Meeting.status == status_filter)
    if participant_id:
        q = q.join(Participant, Meeting.id == Participant.meeting_id).filter(
            Participant.person_id == participant_id
        )
    if date_from:
        q = q.filter(Meeting.scheduled_at >= date_from)
    if date_to:
        q = q.filter(Meeting.scheduled_at <= date_to)
    return q.order_by(Meeting.scheduled_at.desc()).offset(skip).limit(limit).all()


def get_meeting(db: Session, meeting_id: int) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting


def create_meeting(db: Session, data: MeetingCreate) -> Meeting:
    meeting = Meeting(
        title=data.title,
        meeting_type=data.meeting_type,
        scheduled_at=data.scheduled_at,
        agenda=data.agenda,
        raw_notes=data.raw_notes,
        status=MeetingStatus.draft,
    )
    db.add(meeting)
    db.flush()  # get ID before adding participants

    for person_id in data.participant_ids:
        participant = Participant(
            meeting_id=meeting.id,
            person_id=person_id,
            rsvp=RSVP.invited,
        )
        db.add(participant)

    db.commit()
    db.refresh(meeting)
    return meeting


def update_meeting(db: Session, meeting_id: int, data: MeetingUpdate) -> Meeting:
    meeting = get_meeting(db, meeting_id)

    if meeting.status == MeetingStatus.archived:
        raise HTTPException(status_code=409, detail="Cannot update an archived meeting")

    # Optimistic concurrency check
    if data.version != meeting.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {meeting.version}, got {data.version}",
        )

    updates = data.model_dump(exclude_unset=True, exclude={"version"})
    for field, value in updates.items():
        setattr(meeting, field, value)

    meeting.version = meeting.version + 1
    db.commit()
    db.refresh(meeting)
    return meeting


def transition_meeting(
    db: Session,
    meeting_id: int,
    target_status: MeetingStatus,
    reason: str = "",
) -> Meeting:
    meeting = get_meeting(db, meeting_id)
    current = meeting.status
    allowed = VALID_TRANSITIONS.get(current, set())

    if target_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{current}' to '{target_status}'. Allowed: {[s for s in allowed]}",
        )

    meeting.status = target_status
    meeting.version = meeting.version + 1
    db.commit()
    db.refresh(meeting)

    logger.info(
        "meeting.transition",
        meeting_id=meeting_id,
        from_status=current,
        to_status=target_status,
        reason=reason,
    )
    return meeting


def add_participant(db: Session, meeting_id: int, data: ParticipantCreate) -> Participant:
    get_meeting(db, meeting_id)  # 404 guard

    existing = (
        db.query(Participant)
        .filter(
            Participant.meeting_id == meeting_id,
            Participant.person_id == data.person_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Person {data.person_id} is already a participant",
        )

    participant = Participant(
        meeting_id=meeting_id,
        person_id=data.person_id,
        rsvp=data.rsvp,
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def update_participant_rsvp(
    db: Session,
    meeting_id: int,
    person_id: int,
    rsvp: RSVP,
) -> Participant:
    participant = (
        db.query(Participant)
        .filter(
            Participant.meeting_id == meeting_id,
            Participant.person_id == person_id,
        )
        .first()
    )
    if not participant:
        raise HTTPException(
            status_code=404,
            detail=f"Participant person_id={person_id} not found in meeting {meeting_id}",
        )
    participant.rsvp = rsvp
    db.commit()
    db.refresh(participant)
    return participant


def get_meeting_with_open_items(
    db: Session,
    meeting_id: int,
) -> tuple[Meeting, list[ActionItem]]:
    meeting = get_meeting(db, meeting_id)
    open_items = (
        db.query(ActionItem)
        .filter(
            ActionItem.current_meeting_id == meeting_id,
            ActionItem.status.in_([ItemStatus.open, ItemStatus.in_progress, ItemStatus.blocked]),
        )
        .all()
    )
    return meeting, open_items
