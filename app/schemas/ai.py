"""Pydantic schemas for AI features and responses."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import AIRunStatus


# ── Recap ────────────────────────────────────────────────────────────────────

class ExtractedActionItem(BaseModel):
    title: str
    description: str = ""
    owner: str | None = None       # name string (needs resolution)
    due_date: str | None = None    # ISO string or None
    priority: str = "medium"
    confidence: float = 1.0
    source_quote: str = ""


class RecapRequest(BaseModel):
    meeting_id: int
    raw_input: str = Field("", max_length=40000)
    idempotency_key: str = Field("", max_length=200)


class RecapDraft(BaseModel):
    """AI-generated recap draft — not yet committed."""
    summary: str
    decisions: list[str]
    action_items: list[ExtractedActionItem]
    open_questions: list[str]
    risks: list[str]
    ai_generated: bool = True
    ai_run_id: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""


class RecapCommitRequest(BaseModel):
    meeting_id: int
    draft: RecapDraft
    idempotency_key: str = Field(..., min_length=1, max_length=200)
    actor_id: int | None = None


# ── Catch-up brief ───────────────────────────────────────────────────────────

class CatchupRequest(BaseModel):
    person_id: int
    meeting_id: int


class CatchupBrief(BaseModel):
    person_name: str
    meeting_title: str
    what_to_know: str
    expected_of_you: list[str]
    overdue_items: list[str]
    source_meeting_id: int
    ai_generated: bool = True
    ai_run_id: str = ""
    fallback_used: bool = False


# ── KB Linking ────────────────────────────────────────────────────────────────

class KBLinkRequest(BaseModel):
    meeting_id: int | None = None
    item_id: int | None = None
    max_results: int = Field(5, ge=1, le=20)


# ── Nudge ────────────────────────────────────────────────────────────────────

class NudgeRequest(BaseModel):
    item_id: int
    tone: str = Field("friendly", pattern=r"^(friendly|firm)$")
    actor_id: int | None = None


class NudgeResponse(BaseModel):
    item_id: int
    message: str
    tone: str
    ai_generated: bool = True
    ai_run_id: str = ""
    fallback_used: bool = False


# ── Reassignment suggestion ───────────────────────────────────────────────────

class ReassignSuggestRequest(BaseModel):
    item_id: int


class ReassignSuggestion(BaseModel):
    suggested_person_id: int
    suggested_person_name: str
    reason: str
    confidence: float
    ai_run_id: str = ""
    fallback_used: bool = False


# ── AI Run record ─────────────────────────────────────────────────────────────

class AIRunOut(BaseModel):
    id: str
    feature: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: int
    status: AIRunStatus
    attempt_count: int
    prompt_tokens: int | None
    completion_tokens: int | None
    error_type: str
    request_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Risk Radar ────────────────────────────────────────────────────────────────

class RiskSignal(BaseModel):
    signal: str
    description: str


class ItemRisk(BaseModel):
    item_id: int
    item_title: str
    owner_name: str
    risk_score: int   # 0-100
    signals: list[RiskSignal]
    ai_why: str = ""  # AI-generated plain English explanation
    ai_run_id: str = ""


class AgendaAutopilotResponse(BaseModel):
    proposed_agenda: list[str]
    carried_forward_items: list[int]
    unresolved_decisions: list[str]
    open_questions: list[str]
    ai_run_id: str = ""

