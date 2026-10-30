"""AI Endpoints router — recap, commit with idempotency, catch-up brief, KB linking, nudges."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.tasks.catchup import generate_catchup
from app.ai.tasks.kb_link import generate_kb_links
from app.ai.tasks.reassign import suggest_reassignment
from app.ai.tasks.recap import generate_recap
from app.db.models import ActionItem, ItemEventType, ItemStatus, KBDocument, Meeting, Person, Priority
from app.db.session import get_db
from app.logging_config import get_audit_logger, get_logger
from app.schemas.ai import (
    CatchupBrief,
    CatchupRequest,
    KBLinkRequest,
    NudgeRequest,
    NudgeResponse,
    ReassignSuggestion,
    ReassignSuggestRequest,
    RecapCommitRequest,
    RecapDraft,
    RecapRequest,
)
from app.schemas.kb import KBLinkOut
from app.services import kb as kb_svc
from app.services.items import _append_history
from app.services.nudges import generate_nudge_for_item

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = get_logger("routers.ai")
audit = get_audit_logger()


@router.post("/recap", response_model=RecapDraft)
async def create_recap_draft(req: RecapRequest, db: Session = Depends(get_db)):
    """
    Generate structured meeting recap from raw unstructured input.
    Human-in-the-loop: returns a draft for user review, NOT yet committed.
    """
    meeting = db.query(Meeting).filter(Meeting.id == req.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {req.meeting_id} not found")

    raw_text = req.raw_input.strip() or meeting.raw_notes.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="No raw notes or input provided for recap generation")

    # Format participants
    part_names = []
    for p in meeting.participants:
        person = db.query(Person).filter(Person.id == p.person_id).first()
        if person:
            part_names.append(f"{person.name} ({p.rsvp.value})")
    participants_str = ", ".join(part_names) if part_names else "Team"

    draft = await generate_recap(
        meeting_title=meeting.title,
        participants_str=participants_str,
        raw_input=raw_text,
        db=db,
    )
    return draft


@router.post("/recap/commit", response_model=dict)
def commit_recap(req: RecapCommitRequest, db: Session = Depends(get_db)):
    """
    Commit user-reviewed recap to the database.
    Idempotent: double clicks or retries with the same idempotency_key will NOT duplicate items.
    """
    meeting = db.query(Meeting).filter(Meeting.id == req.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {req.meeting_id} not found")

    # Check if this exact idempotency key was already committed
    existing_commit = (
        db.query(ActionItem)
        .filter(ActionItem.idempotency_key == f"recap-{req.idempotency_key}-0")
        .first()
    )
    if existing_commit:
        return {
            "status": "already_committed",
            "message": "This recap was already committed with this idempotency key.",
            "meeting_id": meeting.id,
        }

    # Update meeting fields
    meeting.summary = req.draft.summary
    meeting.decisions = "\n".join(f"- {d}" for d in req.draft.decisions)
    meeting.open_questions = "\n".join(f"- {q}" for q in req.draft.open_questions)
    meeting.risks = "\n".join(f"- {r}" for r in req.draft.risks)
    meeting.ai_generated = True
    meeting.ai_run_id = req.draft.ai_run_id
    meeting.version += 1

    # Persist reviewed action items
    committed_items = []
    for idx, item_data in enumerate(req.draft.action_items):
        item_idem_key = f"recap-{req.idempotency_key}-{idx}"

        # Resolve owner by name if string provided
        resolved_owner_id = None
        if item_data.owner:
            matched_person = (
                db.query(Person)
                .filter(Person.name.ilike(f"%{item_data.owner.strip()}%"))
                .first()
            )
            if matched_person:
                resolved_owner_id = matched_person.id

        # Parse priority enum
        prio = Priority.medium
        try:
            prio = Priority(item_data.priority.lower())
        except Exception:
            pass

        # Parse due date if provided
        parsed_due = None
        if item_data.due_date:
            try:
                parsed_due = datetime.fromisoformat(item_data.due_date.replace("Z", "+00:00"))
            except Exception:
                pass

        action_item = ActionItem(
            title=item_data.title,
            description=item_data.description or "",
            owner_id=resolved_owner_id,
            due_date=parsed_due,
            status=ItemStatus.open,
            priority=prio,
            source_meeting_id=meeting.id,
            current_meeting_id=meeting.id,
            ai_generated=True,
            ai_run_id=req.draft.ai_run_id,
            confidence=item_data.confidence,
            source_quote=item_data.source_quote,
            idempotency_key=item_idem_key,
            version=1,
        )
        db.add(action_item)
        db.flush()

        _append_history(
            db=db,
            item_id=action_item.id,
            event_type=ItemEventType.created,
            actor_id=req.actor_id,
            old_val="",
            new_val=action_item.title,
            note="Created from committed AI recap",
        )
        committed_items.append(action_item.id)

    db.commit()
    audit.info(
        "recap.committed",
        meeting_id=meeting.id,
        items_created=len(committed_items),
        actor_id=req.actor_id,
    )

    return {
        "status": "success",
        "meeting_id": meeting.id,
        "items_created": committed_items,
    }


@router.post("/catchup", response_model=CatchupBrief)
async def get_catchup_brief(req: CatchupRequest, db: Session = Depends(get_db)):
    """Generate a personalised catch-up brief for someone missing a meeting."""
    person = db.query(Person).filter(Person.id == req.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail=f"Person {req.person_id} not found")

    meeting = db.query(Meeting).filter(Meeting.id == req.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {req.meeting_id} not found")

    # Get items from meeting
    items = db.query(ActionItem).filter(ActionItem.current_meeting_id == meeting.id).all()
    action_items_str = "\n".join([f"- {i.title} (Status: {i.status}, Owner: {i.owner_id})" for i in items])

    # Get items owned by this person
    owned = [i for i in items if i.owner_id == person.id]
    owned_str = "\n".join([f"- {i.title} (Due: {i.due_date})" for i in owned]) or "None"

    brief = await generate_catchup(
        person_name=person.name,
        person_role=person.role or "Team Member",
        meeting_title=meeting.title,
        meeting_id=meeting.id,
        summary=meeting.summary or meeting.agenda or meeting.raw_notes[:500],
        decisions=meeting.decisions or "No recorded decisions.",
        action_items_str=action_items_str or "None",
        owned_items_str=owned_str,
        db=db,
    )
    return brief


@router.post("/kb-link", response_model=list[KBLinkOut])
async def link_kb(req: KBLinkRequest, db: Session = Depends(get_db)):
    """Find and rank relevant Knowledge Base documents for a meeting or action item."""
    context_text = ""
    if req.meeting_id:
        m = db.query(Meeting).filter(Meeting.id == req.meeting_id).first()
        if m:
            context_text = f"{m.title}\n{m.agenda}\n{m.summary}\n{m.decisions}"
    elif req.item_id:
        item = db.query(ActionItem).filter(ActionItem.id == req.item_id).first()
        if item:
            context_text = f"{item.title}\n{item.description}"

    if not context_text.strip():
        raise HTTPException(status_code=400, detail="Must provide valid meeting_id or item_id with content")

    # Retrieve candidate KB documents
    docs = db.query(KBDocument).all()
    if not docs:
        return []

    candidates = [
        {"id": d.id, "title": d.title, "content": d.content[:400]}
        for d in docs
    ]

    links_data = await generate_kb_links(
        context_text=context_text,
        kb_candidates=candidates,
        meeting_id=req.meeting_id,
        item_id=req.item_id,
        db=db,
    )

    # Save to database as pending links
    saved_links = kb_svc.save_kb_links(
        db=db,
        links=links_data,
        meeting_id=req.meeting_id,
        item_id=req.item_id,
    )

    res = []
    for l in saved_links:
        doc = db.query(KBDocument).filter(KBDocument.id == l.kb_doc_id).first()
        res.append(
            KBLinkOut(
                id=l.id,
                meeting_id=l.meeting_id,
                item_id=l.item_id,
                kb_doc_id=l.kb_doc_id,
                kb_doc_title=doc.title if doc else "",
                relevance_score=l.relevance_score,
                reason=l.reason,
                accepted=l.accepted,
                ai_run_id=l.ai_run_id,
                created_at=l.created_at,
            )
        )
    return res


@router.post("/nudge", response_model=NudgeResponse)
async def draft_nudge(req: NudgeRequest, db: Session = Depends(get_db)):
    """Draft an AI nudge message for an action item (friendly or firm)."""
    return await generate_nudge_for_item(
        db=db,
        item_id=req.item_id,
        tone=req.tone,
        actor_id=req.actor_id,
    )


@router.post("/reassign-suggest", response_model=ReassignSuggestion)
async def suggest_reassignment_endpoint(
    req: ReassignSuggestRequest, db: Session = Depends(get_db)
):
    """Auto-suggest teammate to reassign item to based on availability and role."""
    item = db.query(ActionItem).filter(ActionItem.id == req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Action item {req.item_id} not found")

    candidates = db.query(Person).filter(Person.is_active.is_(True)).all()
    # Exclude current owner if assigned
    candidates = [p for p in candidates if p.id != item.owner_id]

    return await suggest_reassignment(
        item_title=item.title,
        item_description=item.description,
        candidates=candidates,
        db=db,
    )

