"""Knowledge Base service — document management, search, and linking."""
from __future__ import annotations

import re
from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.db.models import ActionItem, KBDocument, KBLink, Meeting
from app.logging_config import get_audit_logger, get_logger
from app.schemas.kb import KBDocumentCreate, KBDocumentUpdate

logger = get_logger("services.kb")
audit = get_audit_logger()


def list_kb(db: Session, skip: int = 0, limit: int = 50, doc_type: str | None = None) -> list[KBDocument]:
    q = db.query(KBDocument)
    if doc_type:
        q = q.filter(KBDocument.doc_type == doc_type)
    return q.order_by(KBDocument.updated_at.desc()).offset(skip).limit(limit).all()


def get_kb_doc(db: Session, doc_id: int) -> KBDocument:
    doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Knowledge base document {doc_id} not found")
    return doc


def create_kb_doc(db: Session, data: KBDocumentCreate, file_path: str = "") -> KBDocument:
    doc = KBDocument(
        title=data.title,
        content=data.content,
        doc_type=data.doc_type,
        file_path=file_path,
        tags=data.tags,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    audit.info("kb.document_created", doc_id=doc.id, title=doc.title, doc_type=doc.doc_type)
    return doc


def update_kb_doc(db: Session, doc_id: int, data: KBDocumentUpdate) -> KBDocument:
    doc = get_kb_doc(db, doc_id)
    updates = data.model_dump(exclude_unset=True)
    for field, val in updates.items():
        setattr(doc, field, val)
    db.commit()
    db.refresh(doc)
    return doc


def delete_kb_doc(db: Session, doc_id: int) -> None:
    doc = get_kb_doc(db, doc_id)
    db.delete(doc)
    db.commit()
    logger.info("kb.document_deleted", doc_id=doc_id)


def search_kb(db: Session, query: str, limit: int = 10) -> list[KBDocument]:
    """Search KB documents using keyword/token matching across title, content, and tags."""
    if not query.strip():
        return list_kb(db, limit=limit)

    clean_q = query.strip()
    words = re.findall(r"\w+", clean_q.lower())
    if not words:
        words = [clean_q.lower()]

    # Build SQL filter for multiple keywords
    conditions = []
    for w in words[:5]:
        term = f"%{w}%"
        conditions.append(
            or_(
                KBDocument.title.ilike(term),
                KBDocument.content.ilike(term),
                KBDocument.tags.ilike(term),
            )
        )

    q = db.query(KBDocument).filter(*conditions).limit(limit)
    return q.all()


def accept_reject_link(db: Session, link_id: int, accepted: bool) -> KBLink:
    link = db.query(KBLink).filter(KBLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail=f"KB link {link_id} not found")
    link.accepted = accepted
    db.commit()
    db.refresh(link)
    audit.info("kb.link_decision", link_id=link.id, accepted=accepted)
    return link


def save_kb_links(
    db: Session,
    links: list[dict],
    meeting_id: int | None = None,
    item_id: int | None = None,
    ai_run_id: str | None = None,
) -> list[KBLink]:
    created_links: list[KBLink] = []
    for link_data in links:
        doc_id = link_data.get("kb_doc_id")
        if not doc_id:
            continue
        # Verify doc exists
        doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
        if not doc:
            continue

        # Prevent duplicate link
        existing = db.query(KBLink).filter(
            KBLink.kb_doc_id == doc_id,
            KBLink.meeting_id == meeting_id if meeting_id else KBLink.meeting_id.is_(None),
            KBLink.item_id == item_id if item_id else KBLink.item_id.is_(None),
        ).first()

        if existing:
            existing.relevance_score = link_data.get("relevance_score", existing.relevance_score)
            existing.reason = link_data.get("reason", existing.reason)
            created_links.append(existing)
            continue

        kb_link = KBLink(
            meeting_id=meeting_id,
            item_id=item_id,
            kb_doc_id=doc_id,
            relevance_score=link_data.get("relevance_score", 0.0),
            reason=link_data.get("reason", ""),
            accepted=None,  # Pending user review
            ai_run_id=ai_run_id,
        )
        db.add(kb_link)
        created_links.append(kb_link)

    db.commit()
    for l in created_links:
        db.refresh(l)
    return created_links

