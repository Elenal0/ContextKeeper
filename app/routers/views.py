"""Web views router — serves responsive server-rendered HTML UI using Jinja2."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ActionItem, Availability, KBDocument, KBLink, Meeting, MeetingStatus, Person
from app.db.session import get_db
from app.services.nudges import get_risk_radar

router = APIRouter(tags=["views"])

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Humanizing Jinja Filters ──────────────────────────────────────────────────

def human_status(val: Any) -> str:
    if not val:
        return "Unknown"
    s = getattr(val, "value", str(val))
    if "." in s:
        s = s.split(".")[-1]
    mapping = {
        "draft": "Draft",
        "scheduled": "Scheduled",
        "in_progress": "In Progress",
        "completed": "Completed",
        "archived": "Archived",
        "cancelled": "Cancelled",
        "open": "Open",
        "blocked": "Blocked",
        "done": "Done",
    }
    return mapping.get(s.lower(), s.replace("_", " ").title())


def human_type(val: Any) -> str:
    if not val:
        return "Meeting"
    s = getattr(val, "value", str(val))
    if "." in s:
        s = s.split(".")[-1]
    mapping = {"meeting": "Meeting", "handover": "Work Handover"}
    return mapping.get(s.lower(), s.replace("_", " ").title())


def human_rsvp(val: Any) -> str:
    if not val:
        return "Invited"
    s = getattr(val, "value", str(val))
    if "." in s:
        s = s.split(".")[-1]
    mapping = {
        "invited": "Invited",
        "accepted": "Accepted",
        "declined": "Declined",
        "no_response": "No Response",
        "attended": "Attended",
        "absent": "Absent",
    }
    return mapping.get(s.lower(), s.replace("_", " ").title())


def human_priority(val: Any) -> str:
    if not val:
        return "Medium"
    s = getattr(val, "value", str(val))
    if "." in s:
        s = s.split(".")[-1]
    return s.capitalize()


def human_date(val: Any) -> str:
    if not val:
        return "TBD"
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return val
    return val.strftime("%b %d, %Y, %I:%M %p")


def time_ago_or_left(val: Any) -> str:
    if not val:
        return ""
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return ""
    now = datetime.now(val.tzinfo or timezone.utc)
    if val.tzinfo is None:
        val = val.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
    diff = (val - now).total_seconds()
    days = int(diff / 86400)
    if days > 1:
        return f"in {days} days"
    elif days == 1:
        return "tomorrow"
    elif days == 0 and diff > 0:
        return "today"
    elif days == 0 and diff <= 0:
        return "earlier today"
    elif days == -1:
        return "yesterday"
    else:
        return f"{abs(days)} days ago"


def format_initials(name: str) -> str:
    if not name:
        return "??"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


templates.env.filters["human_status"] = human_status
templates.env.filters["human_type"] = human_type
templates.env.filters["human_rsvp"] = human_rsvp
templates.env.filters["human_priority"] = human_priority
templates.env.filters["human_date"] = human_date
templates.env.filters["time_ago_or_left"] = time_ago_or_left
templates.env.filters["initials"] = format_initials


# ── View Endpoints ────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    radar_items = get_risk_radar(db)
    radar_items_json = json.dumps([r.model_dump() for r in radar_items], default=str)

    people_on_leave = (
        db.query(Person)
        .filter(Person.is_active.is_(True), Person.availability == Availability.on_leave)
        .all()
    )

    upcoming_meetings = (
        db.query(Meeting)
        .filter(Meeting.status.in_([MeetingStatus.scheduled, MeetingStatus.in_progress]))
        .order_by(Meeting.scheduled_at.asc().nulls_last())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "ai_provider": settings.effective_ai_provider(),
            "radar_items_json": radar_items_json,
            "people_on_leave": people_on_leave,
            "upcoming_meetings": upcoming_meetings,
        },
    )


@router.get("/meetings", response_class=HTMLResponse)
def view_meetings(request: Request, db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    meetings_data = []
    for m in meetings:
        open_items = (
            db.query(ActionItem)
            .filter(
                ActionItem.current_meeting_id == m.id,
                ActionItem.status.in_(["open", "in_progress", "blocked"]),
            )
            .count()
        )
        meetings_data.append({
            "id": m.id,
            "title": m.title,
            "meeting_type": human_type(m.meeting_type),
            "raw_type": getattr(m.meeting_type, "value", str(m.meeting_type)),
            "status": human_status(m.status),
            "raw_status": getattr(m.status, "value", str(m.status)),
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
            "participant_count": len(m.participants),
            "open_item_count": open_items,
        })

    return templates.TemplateResponse(
        request=request,
        name="meetings.html",
        context={
            "active_page": "meetings",
            "ai_provider": settings.effective_ai_provider(),
            "meetings_json": json.dumps(meetings_data),
        },
    )


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
def view_meeting_detail(meeting_id: int, request: Request, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return HTMLResponse("Meeting not found", status_code=404)

    items = db.query(ActionItem).filter(ActionItem.current_meeting_id == meeting.id).all()
    items_data = []
    for i in items:
        owner = db.query(Person).filter(Person.id == i.owner_id).first() if i.owner_id else None
        items_data.append({
            "id": i.id,
            "title": i.title,
            "owner_name": owner.name if owner else "Unassigned",
            "owner_initials": format_initials(owner.name if owner else "Unassigned"),
            "status": human_status(i.status),
            "raw_status": getattr(i.status, "value", str(i.status)),
            "priority": human_priority(i.priority),
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "carry_forward_count": i.carry_forward_count,
            "ai_generated": i.ai_generated,
        })

    participants_data = []
    for p in meeting.participants:
        person = db.query(Person).filter(Person.id == p.person_id).first()
        participants_data.append({
            "id": p.id,
            "person_id": p.person_id,
            "person_name": person.name if person else "Unknown",
            "person_initials": format_initials(person.name if person else "Unknown"),
            "person_email": person.email if person else "",
            "rsvp": human_rsvp(p.rsvp),
            "raw_rsvp": getattr(p.rsvp, "value", str(p.rsvp)),
        })

    kb_links = db.query(KBLink).filter(KBLink.meeting_id == meeting.id).all()
    kb_data = []
    for l in kb_links:
        doc = db.query(KBDocument).filter(KBDocument.id == l.kb_doc_id).first()
        kb_data.append({
            "id": l.id,
            "kb_doc_id": l.kb_doc_id,
            "kb_doc_title": doc.title if doc else "",
            "relevance_score": l.relevance_score,
            "reason": l.reason,
            "accepted": l.accepted,
        })

    return templates.TemplateResponse(
        request=request,
        name="meeting_detail.html",
        context={
            "active_page": "meetings",
            "ai_provider": settings.effective_ai_provider(),
            "meeting": meeting,
            "items_json": json.dumps(items_data),
            "participants_json": json.dumps(participants_data),
            "kb_links_json": json.dumps(kb_data),
        },
    )


@router.get("/items", response_class=HTMLResponse)
def view_items(request: Request, db: Session = Depends(get_db)):
    items = db.query(ActionItem).order_by(ActionItem.created_at.desc()).all()
    items_data = []
    for i in items:
        owner = db.query(Person).filter(Person.id == i.owner_id).first() if i.owner_id else None
        items_data.append({
            "id": i.id,
            "title": i.title,
            "owner_id": i.owner_id,
            "owner_name": owner.name if owner else "Unassigned",
            "owner_initials": format_initials(owner.name if owner else "Unassigned"),
            "status": human_status(i.status),
            "raw_status": getattr(i.status, "value", str(i.status)),
            "priority": human_priority(i.priority),
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "carry_forward_count": i.carry_forward_count,
            "ai_generated": i.ai_generated,
        })

    return templates.TemplateResponse(
        request=request,
        name="items.html",
        context={
            "active_page": "items",
            "ai_provider": settings.effective_ai_provider(),
            "items_json": json.dumps(items_data),
        },
    )


@router.get("/catchup", response_class=HTMLResponse)
def view_catchup(request: Request, db: Session = Depends(get_db)):
    people = db.query(Person).filter(Person.is_active.is_(True)).all()
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="catchup.html",
        context={
            "active_page": "catchup",
            "ai_provider": settings.effective_ai_provider(),
            "people": people,
            "meetings": meetings,
        },
    )


@router.get("/kb", response_class=HTMLResponse)
def view_kb(request: Request, db: Session = Depends(get_db)):
    docs = db.query(KBDocument).order_by(KBDocument.updated_at.desc()).all()
    docs_data = [
        {
            "id": d.id,
            "title": d.title,
            "content": d.content,
            "doc_type": d.doc_type,
            "tags": d.tags,
            "updated_at": d.updated_at.isoformat() if d.updated_at else "",
        }
        for d in docs
    ]

    return templates.TemplateResponse(
        request=request,
        name="kb.html",
        context={
            "active_page": "kb",
            "ai_provider": settings.effective_ai_provider(),
            "docs_json": json.dumps(docs_data),
        },
    )


@router.get("/admin-ui", response_class=HTMLResponse)
def view_admin(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "active_page": "admin",
            "ai_provider": settings.effective_ai_provider(),
        },
    )
