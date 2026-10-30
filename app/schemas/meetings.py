"""Pydantic schemas for Meetings and Participants."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import MeetingStatus, MeetingType, RSVP


class ParticipantBase(BaseModel):
    person_id: int
    rsvp: RSVP = RSVP.invited


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantUpdate(BaseModel):
    rsvp: RSVP


class ParticipantOut(ParticipantBase):
    id: int
    meeting_id: int
    person_name: str = ""
    person_email: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    meeting_type: MeetingType = MeetingType.meeting
    scheduled_at: datetime | None = None
    agenda: str = ""
    raw_notes: str = ""


class MeetingCreate(MeetingBase):
    participant_ids: list[int] = []


class MeetingUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    meeting_type: MeetingType | None = None
    scheduled_at: datetime | None = None
    agenda: str | None = None
    raw_notes: str | None = None
    summary: str | None = None
    decisions: str | None = None
    open_questions: str | None = None
    risks: str | None = None
    version: int  # optimistic concurrency


class TransitionRequest(BaseModel):
    target_status: MeetingStatus
    reason: str = ""


class MeetingOut(MeetingBase):
    id: int
    status: MeetingStatus
    summary: str
    decisions: str
    open_questions: str
    risks: str
    ai_generated: bool
    ai_run_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    participants: list[ParticipantOut] = []

    model_config = {"from_attributes": True}


class MeetingListOut(BaseModel):
    id: int
    title: str
    meeting_type: MeetingType
    status: MeetingStatus
    scheduled_at: datetime | None
    participant_count: int = 0
    open_item_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CarryForwardRequest(BaseModel):
    target_meeting_id: int
    item_ids: list[int]  # which items to carry forward
    actor_id: int | None = None


class AgendaAutopilotRequest(BaseModel):
    previous_meeting_id: int
    max_items: int = Field(10, ge=1, le=50)

