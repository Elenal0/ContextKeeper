"""Pydantic schemas for Action Items and Item History."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import ItemEventType, ItemStatus, Priority, ResolutionType


class ItemHistoryOut(BaseModel):
    id: int
    item_id: int
    event_type: ItemEventType
    actor_id: int | None
    actor_name: str = ""
    old_value: str
    new_value: str
    note: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class ActionItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    owner_id: int | None = None
    due_date: datetime | None = None
    priority: Priority = Priority.medium
    source_meeting_id: int | None = None
    current_meeting_id: int | None = None


class ActionItemCreate(ActionItemBase):
    actor_id: int | None = None


class ActionItemUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    owner_id: int | None = None
    due_date: datetime | None = None
    priority: Priority | None = None
    status: ItemStatus | None = None
    current_meeting_id: int | None = None
    version: int  # optimistic concurrency
    actor_id: int | None = None


class CloseItemRequest(BaseModel):
    outcome: str = Field(..., min_length=1, max_length=2000)
    resolution_type: ResolutionType
    actor_id: int | None = None


class ReassignRequest(BaseModel):
    new_owner_id: int
    actor_id: int | None = None
    note: str = ""


class ActionItemOut(ActionItemBase):
    id: int
    status: ItemStatus
    outcome: str
    resolution_type: ResolutionType | None
    carry_forward_count: int
    ai_generated: bool
    ai_run_id: str | None
    confidence: float | None
    source_quote: str
    version: int
    created_at: datetime
    closed_at: datetime | None
    updated_at: datetime
    owner_name: str = ""
    history: list[ItemHistoryOut] = []

    model_config = {"from_attributes": True}


class ActionItemListOut(BaseModel):
    id: int
    title: str
    status: ItemStatus
    priority: Priority
    owner_id: int | None
    owner_name: str = ""
    due_date: datetime | None
    carry_forward_count: int
    source_meeting_id: int | None
    current_meeting_id: int | None
    ai_generated: bool
    created_at: datetime

    model_config = {"from_attributes": True}

