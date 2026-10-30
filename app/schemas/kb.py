"""Pydantic schemas for Knowledge Base."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KBDocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    doc_type: str = Field("document", pattern=r"^(runbook|adr|policy|onboarding|postmortem|document)$")
    tags: str = ""


class KBDocumentCreate(KBDocumentBase):
    pass


class KBDocumentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = None
    doc_type: str | None = None
    tags: str | None = None


class KBDocumentOut(KBDocumentBase):
    id: int
    file_path: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBLinkOut(BaseModel):
    id: int
    meeting_id: int | None
    item_id: int | None
    kb_doc_id: int
    kb_doc_title: str = ""
    relevance_score: float
    reason: str
    accepted: bool | None
    ai_run_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class KBLinkAcceptRequest(BaseModel):
    accepted: bool


class KBSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=50)

