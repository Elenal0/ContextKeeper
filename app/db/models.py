"""
All ORM models for ContextKeeper.

Tables:
  people, meetings, participants, action_items,
  item_history, kb_documents, kb_links, ai_runs
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class Availability(str, enum.Enum):
    available = "available"
    on_leave = "on_leave"


class MeetingType(str, enum.Enum):
    meeting = "meeting"
    handover = "handover"


class MeetingStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    archived = "archived"
    cancelled = "cancelled"


class RSVP(str, enum.Enum):
    invited = "invited"
    accepted = "accepted"
    declined = "declined"
    no_response = "no_response"
    attended = "attended"
    absent = "absent"


class ItemStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ResolutionType(str, enum.Enum):
    completed = "completed"
    dropped = "dropped"
    superseded = "superseded"
    deferred = "deferred"


class ItemEventType(str, enum.Enum):
    created = "created"
    reassigned = "reassigned"
    status_changed = "status_changed"
    carried_forward = "carried_forward"
    due_date_changed = "due_date_changed"
    outcome_recorded = "outcome_recorded"
    priority_changed = "priority_changed"
    edited = "edited"


class AIRunStatus(str, enum.Enum):
    success = "success"
    retry = "retry"
    fallback = "fallback"
    error = "error"


# ── People ────────────────────────────────────────────────────────────────────

class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    availability: Mapped[str] = mapped_column(
        Enum(Availability), default=Availability.available, nullable=False
    )
    leave_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    leave_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    participations: Mapped[list["Participant"]] = relationship(
        back_populates="person", lazy="select"
    )
    owned_items: Mapped[list["ActionItem"]] = relationship(
        "ActionItem", foreign_keys="ActionItem.owner_id", back_populates="owner", lazy="select"
    )


# ── Meetings ──────────────────────────────────────────────────────────────────

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    meeting_type: Mapped[str] = mapped_column(
        Enum(MeetingType), default=MeetingType.meeting, nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.draft, nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    agenda: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    decisions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    open_questions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risks: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", lazy="select"
    )
    source_items: Mapped[list["ActionItem"]] = relationship(
        "ActionItem", foreign_keys="ActionItem.source_meeting_id",
        back_populates="source_meeting", lazy="select"
    )
    current_items: Mapped[list["ActionItem"]] = relationship(
        "ActionItem", foreign_keys="ActionItem.current_meeting_id",
        back_populates="current_meeting", lazy="select"
    )
    kb_links: Mapped[list["KBLink"]] = relationship(
        "KBLink", foreign_keys="KBLink.meeting_id",
        back_populates="meeting", lazy="select"
    )


# ── Valid lifecycle transitions ───────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, set[str]] = {
    MeetingStatus.draft: {MeetingStatus.scheduled, MeetingStatus.cancelled},
    MeetingStatus.scheduled: {MeetingStatus.in_progress, MeetingStatus.cancelled},
    MeetingStatus.in_progress: {MeetingStatus.completed, MeetingStatus.cancelled},
    MeetingStatus.completed: {MeetingStatus.archived},
    MeetingStatus.archived: set(),
    MeetingStatus.cancelled: set(),
}


# ── Participants ──────────────────────────────────────────────────────────────

class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    rsvp: Mapped[str] = mapped_column(
        Enum(RSVP), default=RSVP.invited, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(back_populates="participants")
    person: Mapped["Person"] = relationship(back_populates="participations")

    __table_args__ = (
        Index("ix_participants_meeting_person", "meeting_id", "person_id", unique=True),
    )


# ── Action Items ──────────────────────────────────────────────────────────────

class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(ItemStatus), default=ItemStatus.open, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        Enum(Priority), default=Priority.medium, nullable=False
    )
    source_meeting_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    current_meeting_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(Text, default="", nullable=False)
    resolution_type: Mapped[str | None] = mapped_column(
        Enum(ResolutionType), nullable=True
    )
    carry_forward_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_quote: Mapped[str] = mapped_column(Text, default="", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    owner: Mapped["Person | None"] = relationship(
        "Person", foreign_keys=[owner_id], back_populates="owned_items"
    )
    source_meeting: Mapped["Meeting | None"] = relationship(
        "Meeting", foreign_keys=[source_meeting_id], back_populates="source_items"
    )
    current_meeting: Mapped["Meeting | None"] = relationship(
        "Meeting", foreign_keys=[current_meeting_id], back_populates="current_items"
    )
    history: Mapped[list["ItemHistory"]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="ItemHistory.timestamp", lazy="select"
    )
    kb_links: Mapped[list["KBLink"]] = relationship(
        "KBLink", foreign_keys="KBLink.item_id",
        back_populates="item", lazy="select"
    )

    __table_args__ = (
        Index("ix_items_owner_status", "owner_id", "status"),
        Index("ix_items_due_date", "due_date"),
        Index("ix_items_current_meeting", "current_meeting_id"),
        Index("ix_items_status", "status"),
    )


# ── Item History (append-only) ────────────────────────────────────────────────

class ItemHistory(Base):
    __tablename__ = "item_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("action_items.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        Enum(ItemEventType), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    old_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    item: Mapped["ActionItem"] = relationship(back_populates="history")
    actor: Mapped["Person | None"] = relationship("Person", foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_item_history_item_id", "item_id"),
        Index("ix_item_history_timestamp", "timestamp"),
    )


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KBDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(50), default="document", nullable=False
    )  # runbook, adr, policy, onboarding, postmortem, document
    file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="", nullable=False)  # comma-sep
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    kb_links: Mapped[list["KBLink"]] = relationship(
        back_populates="kb_document", cascade="all, delete-orphan", lazy="select"
    )


class KBLink(Base):
    __tablename__ = "kb_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=True
    )
    item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("action_items.id", ondelete="CASCADE"), nullable=True
    )
    kb_doc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False
    )
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None=pending
    ai_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    meeting: Mapped["Meeting | None"] = relationship(
        "Meeting", foreign_keys=[meeting_id], back_populates="kb_links"
    )
    item: Mapped["ActionItem | None"] = relationship(
        "ActionItem", foreign_keys=[item_id], back_populates="kb_links"
    )
    kb_document: Mapped["KBDocument"] = relationship(back_populates="kb_links")


# ── AI Runs ───────────────────────────────────────────────────────────────────

class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(AIRunStatus), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ai_runs_feature", "feature"),
        Index("ix_ai_runs_created_at", "created_at"),
    )

