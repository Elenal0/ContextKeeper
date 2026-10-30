"""Meetings & Handovers router."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import ActionItem, ItemStatus, Meeting, Person
from app.db.session import get_db
from app.schemas.ai import AgendaAutopilotResponse
from app.schemas.items import ActionItemOut
from app.schemas.meetings import (
    AgendaAutopilotRequest,
    CarryForwardRequest,
    MeetingCreate,
    MeetingListOut,
    MeetingOut,
    MeetingUpdate,
    ParticipantCreate,
    ParticipantOut,
    ParticipantUpdate,
    TransitionRequest,
)
from app.services import carry_forward as carry_svc
from app.services import meetings as meetings_svc
from app.services.nudges import get_risk_radar

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingListOut])
def list_meetings(
    type_filter: str | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status"),
    participant_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    meetings = meetings_svc.list_meetings(
        db,
        type_filter=type_filter,
        status_filter=status_filter,
        participant_id=participant_id,
        skip=skip,
        limit=limit,
    )
    res = []
    for m in meetings:
        p_count = len(m.participants)
        open_items = (
            db.query(ActionItem)
            .filter(
                ActionItem.current_meeting_id == m.id,
                ActionItem.status.in_([ItemStatus.open, ItemStatus.in_progress, ItemStatus.blocked]),
            )
            .count()
        )
        res.append(
            MeetingListOut(
                id=m.id,
                title=m.title,
                meeting_type=m.meeting_type,
                status=m.status,
                scheduled_at=m.scheduled_at,
                participant_count=p_count,
                open_item_count=open_items,
                created_at=m.created_at,
            )
        )
    return res


@router.post("", response_model=MeetingOut, status_code=201)
def create_meeting(data: MeetingCreate, db: Session = Depends(get_db)):
    m = meetings_svc.create_meeting(db, data)
    return get_meeting(m.id, db)


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    try:
        m = meetings_svc.get_meeting(db, meeting_id)
        # Format participant out models with person details
        parts = []
        for p in m.participants:
            person = db.query(Person).filter(Person.id == p.person_id).first()
            parts.append(
                ParticipantOut(
                    id=p.id,
                    meeting_id=p.meeting_id,
                    person_id=p.person_id,
                    person_name=person.name if person else "",
                    person_email=person.email if person else "",
                    rsvp=p.rsvp,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return MeetingOut(
            id=m.id,
            title=m.title,
            meeting_type=m.meeting_type,
            status=m.status,
            scheduled_at=m.scheduled_at,
            agenda=m.agenda,
            raw_notes=m.raw_notes,
            summary=m.summary,
            decisions=m.decisions,
            open_questions=m.open_questions,
            risks=m.risks,
            ai_generated=m.ai_generated,
            ai_run_id=m.ai_run_id,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
            participants=parts,
        )
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{meeting_id}", response_model=MeetingOut)
def update_meeting(meeting_id: int, data: MeetingUpdate, db: Session = Depends(get_db)):
    try:
        meetings_svc.update_meeting(db, meeting_id, data)
        return get_meeting(meeting_id, db)
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except meetings_svc.ArchivedMeetingEdit as e:
        raise HTTPException(status_code=400, detail=str(e))
    except meetings_svc.OptimisticLockError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{meeting_id}/transition", response_model=MeetingOut)
def transition_meeting(meeting_id: int, req: TransitionRequest, db: Session = Depends(get_db)):
    try:
        meetings_svc.transition_meeting(db, meeting_id, req.target_status.value, req.reason)
        return get_meeting(meeting_id, db)
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except meetings_svc.InvalidTransition as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{meeting_id}/participants", response_model=list[ParticipantOut])
def get_participants(meeting_id: int, db: Session = Depends(get_db)):
    try:
        parts = meetings_svc.get_participants(db, meeting_id)
        result = []
        for p in parts:
            person = db.query(Person).filter(Person.id == p.person_id).first()
            result.append(
                ParticipantOut(
                    id=p.id,
                    meeting_id=p.meeting_id,
                    person_id=p.person_id,
                    person_name=person.name if person else "",
                    person_email=person.email if person else "",
                    rsvp=p.rsvp,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return result
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{meeting_id}/participants", response_model=ParticipantOut)
def add_participant(meeting_id: int, data: ParticipantCreate, db: Session = Depends(get_db)):
    try:
        p = meetings_svc.add_participant(db, meeting_id, data)
        person = db.query(Person).filter(Person.id == p.person_id).first()
        return ParticipantOut(
            id=p.id,
            meeting_id=p.meeting_id,
            person_id=p.person_id,
            person_name=person.name if person else "",
            person_email=person.email if person else "",
            rsvp=p.rsvp,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except meetings_svc.DuplicateParticipant as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{meeting_id}/participants/{person_id}", response_model=ParticipantOut)
def update_participant_rsvp(
    meeting_id: int, person_id: int, data: ParticipantUpdate, db: Session = Depends(get_db)
):
    try:
        p = meetings_svc.update_participant_rsvp(db, meeting_id, person_id, data.rsvp.value)
        person = db.query(Person).filter(Person.id == p.person_id).first()
        return ParticipantOut(
            id=p.id,
            meeting_id=p.meeting_id,
            person_id=p.person_id,
            person_name=person.name if person else "",
            person_email=person.email if person else "",
            rsvp=p.rsvp,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
    except meetings_svc.MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{meeting_id}/carry-forward", response_model=list[dict])
def carry_forward_to_meeting(meeting_id: int, req: CarryForwardRequest, db: Session = Depends(get_db)):
    items = carry_svc.carry_forward_items(
        db=db,
        item_ids=req.item_ids,
        target_meeting_id=meeting_id,
        actor_id=req.actor_id,
    )
    return [{"id": i.id, "title": i.title, "carry_forward_count": i.carry_forward_count} for i in items]


@router.post("/{meeting_id}/agenda-autopilot", response_model=AgendaAutopilotResponse)
def agenda_autopilot(meeting_id: int, req: AgendaAutopilotRequest, db: Session = Depends(get_db)):
    """
    Agenda Autopilot: Propose next meeting's agenda from open items sorted by risk score
    + unresolved decisions and open questions from the previous recap.
    """
    prev_meeting = db.query(Meeting).filter(Meeting.id == req.previous_meeting_id).first()
    if not prev_meeting:
        raise HTTPException(status_code=404, detail=f"Previous meeting {req.previous_meeting_id} not found")

    # Get risk radar to rank open items
    risk_items = get_risk_radar(db)
    # Filter items from or currently in the previous meeting
    relevant_open = [
        r for r in risk_items
        if db.query(ActionItem).filter(
            ActionItem.id == r.item_id,
            (ActionItem.current_meeting_id == prev_meeting.id) | (ActionItem.source_meeting_id == prev_meeting.id),
        ).first() is not None
    ][: req.max_items]

    proposed_agenda: list[str] = [
        f"Review minutes & actions from previous session: '{prev_meeting.title}' (10 min)",
    ]

    for item in relevant_open:
        proposed_agenda.append(
            f"Action Review: '{item.item_title}' (Owner: {item.owner_name}, Risk Score: {item.risk_score}/100)"
        )

    # Decisions to revisit
    unresolved_decisions: list[str] = []
    if prev_meeting.decisions:
        for line in prev_meeting.decisions.splitlines():
            line = line.strip().lstrip("-*• ")
            if line:
                unresolved_decisions.append(line)
        if unresolved_decisions:
            proposed_agenda.append("Check-in on previous decisions status (10 min)")

    # Open questions
    open_questions: list[str] = []
    if prev_meeting.open_questions:
        for line in prev_meeting.open_questions.splitlines():
            line = line.strip().lstrip("-*• ")
            if line:
                open_questions.append(line)
        if open_questions:
            proposed_agenda.append(f"Resolve outstanding open questions ({len(open_questions)} items)")

    proposed_agenda.append("Wrap-up & next steps assignment (5 min)")

    return AgendaAutopilotResponse(
        proposed_agenda=proposed_agenda,
        carried_forward_items=[r.item_id for r in relevant_open],
        unresolved_decisions=unresolved_decisions,
        open_questions=open_questions,
        ai_run_id="",
    )

