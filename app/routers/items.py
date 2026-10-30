"""Action Items router — full tracking, closure with outcome, reassignment, and history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import ActionItem, ItemHistory, Person
from app.db.session import get_db
from app.schemas.items import (
    ActionItemCreate,
    ActionItemListOut,
    ActionItemOut,
    ActionItemUpdate,
    CloseItemRequest,
    ItemHistoryOut,
    ReassignRequest,
)
from app.services import items as items_svc

router = APIRouter(prefix="/api/items", tags=["items"])


def _to_item_out(db: Session, item: ActionItem) -> ActionItemOut:
    owner = db.query(Person).filter(Person.id == item.owner_id).first() if item.owner_id else None
    owner_name = owner.name if owner else ""

    history_records = (
        db.query(ItemHistory)
        .filter(ItemHistory.item_id == item.id)
        .order_by(ItemHistory.timestamp.asc())
        .all()
    )
    history_outs = []
    for h in history_records:
        actor = db.query(Person).filter(Person.id == h.actor_id).first() if h.actor_id else None
        history_outs.append(
            ItemHistoryOut(
                id=h.id,
                item_id=h.item_id,
                event_type=h.event_type,
                actor_id=h.actor_id,
                actor_name=actor.name if actor else "",
                old_value=h.old_value,
                new_value=h.new_value,
                note=h.note,
                timestamp=h.timestamp,
            )
        )

    return ActionItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        owner_id=item.owner_id,
        owner_name=owner_name,
        due_date=item.due_date,
        priority=item.priority,
        status=item.status,
        source_meeting_id=item.source_meeting_id,
        current_meeting_id=item.current_meeting_id,
        outcome=item.outcome,
        resolution_type=item.resolution_type,
        carry_forward_count=item.carry_forward_count,
        ai_generated=item.ai_generated,
        ai_run_id=item.ai_run_id,
        confidence=item.confidence,
        source_quote=item.source_quote,
        version=item.version,
        created_at=item.created_at,
        closed_at=item.closed_at,
        updated_at=item.updated_at,
        history=history_outs,
    )


@router.get("", response_model=list[ActionItemListOut])
def list_items(
    owner_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    meeting_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items = items_svc.list_items(
        db,
        owner_id=owner_id,
        status=status,
        priority=priority,
        meeting_id=meeting_id,
        skip=skip,
        limit=limit,
    )
    res = []
    for i in items:
        owner = db.query(Person).filter(Person.id == i.owner_id).first() if i.owner_id else None
        res.append(
            ActionItemListOut(
                id=i.id,
                title=i.title,
                status=i.status,
                priority=i.priority,
                owner_id=i.owner_id,
                owner_name=owner.name if owner else "Unassigned",
                due_date=i.due_date,
                carry_forward_count=i.carry_forward_count,
                source_meeting_id=i.source_meeting_id,
                current_meeting_id=i.current_meeting_id,
                ai_generated=i.ai_generated,
                created_at=i.created_at,
            )
        )
    return res


@router.post("", response_model=ActionItemOut, status_code=201)
def create_item(data: ActionItemCreate, db: Session = Depends(get_db)):
    item = items_svc.create_item(db, data)
    return _to_item_out(db, item)


@router.get("/{item_id}", response_model=ActionItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = items_svc.get_item(db, item_id)
    return _to_item_out(db, item)


@router.put("/{item_id}", response_model=ActionItemOut)
def update_item(item_id: int, data: ActionItemUpdate, db: Session = Depends(get_db)):
    item = items_svc.update_item(db, item_id, data)
    return _to_item_out(db, item)


@router.post("/{item_id}/close", response_model=ActionItemOut)
def close_item(item_id: int, req: CloseItemRequest, db: Session = Depends(get_db)):
    """Close an action item — outcome and resolution_type are strictly mandatory."""
    item = items_svc.close_item(
        db=db,
        item_id=item_id,
        outcome=req.outcome,
        resolution_type=req.resolution_type,
        actor_id=req.actor_id,
    )
    return _to_item_out(db, item)


@router.post("/{item_id}/reassign", response_model=ActionItemOut)
def reassign_item(item_id: int, req: ReassignRequest, db: Session = Depends(get_db)):
    item = items_svc.reassign_item(
        db=db,
        item_id=item_id,
        new_owner_id=req.new_owner_id,
        actor_id=req.actor_id,
        note=req.note,
    )
    return _to_item_out(db, item)


@router.get("/{item_id}/history", response_model=list[ItemHistoryOut])
def get_history(item_id: int, db: Session = Depends(get_db)):
    items_svc.get_item(db, item_id)  # verify existence
    history_records = items_svc.get_item_history(db, item_id)
    res = []
    for h in history_records:
        actor = db.query(Person).filter(Person.id == h.actor_id).first() if h.actor_id else None
        res.append(
            ItemHistoryOut(
                id=h.id,
                item_id=h.item_id,
                event_type=h.event_type,
                actor_id=h.actor_id,
                actor_name=actor.name if actor else "",
                old_value=h.old_value,
                new_value=h.new_value,
                note=h.note,
                timestamp=h.timestamp,
            )
        )
    return res

