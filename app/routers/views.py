"""Web views router — serves responsive server-rendered HTML UI using Jinja2."""
from __future__ import annotations

import json
from pathlib import Path
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
            "meeting_type": m.meeting_type,
            "status": m.status,
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
            "status": i.status,
            "priority": i.priority,
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
            "person_email": person.email if person else "",
            "rsvp": p.rsvp,
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
            "status": i.status,
            "priority": i.priority,
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
