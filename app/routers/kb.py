"""Knowledge Base router — docs, search, link decisions, and file uploads."""
from __future__ import annotations

import os
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import KBDocument, KBLink
from app.db.session import get_db
from app.schemas.kb import (
    KBDocumentCreate,
    KBDocumentOut,
    KBDocumentUpdate,
    KBLinkAcceptRequest,
    KBLinkOut,
)
from app.services import kb as kb_svc

router = APIRouter(prefix="/api/kb", tags=["kb"])


@router.get("", response_model=list[KBDocumentOut])
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    doc_type: str | None = None,
    db: Session = Depends(get_db),
):
    return kb_svc.list_kb(db, skip=skip, limit=limit, doc_type=doc_type)


@router.post("", response_model=KBDocumentOut, status_code=201)
def create_document(data: KBDocumentCreate, db: Session = Depends(get_db)):
    return kb_svc.create_kb_doc(db, data)


@router.get("/search", response_model=list[KBDocumentOut])
def search_documents(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return kb_svc.search_kb(db, query=query, limit=limit)


@router.get("/{doc_id}", response_model=KBDocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return kb_svc.get_kb_doc(db, doc_id)


@router.put("/{doc_id}", response_model=KBDocumentOut)
def update_document(doc_id: int, data: KBDocumentUpdate, db: Session = Depends(get_db)):
    return kb_svc.update_kb_doc(db, doc_id, data)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    kb_svc.delete_kb_doc(db, doc_id)


@router.put("/links/{link_id}", response_model=KBLinkOut)
def decide_link(link_id: int, req: KBLinkAcceptRequest, db: Session = Depends(get_db)):
    link = kb_svc.accept_reject_link(db, link_id, req.accepted)
    doc = db.query(KBDocument).filter(KBDocument.id == link.kb_doc_id).first()
    return KBLinkOut(
        id=link.id,
        meeting_id=link.meeting_id,
        item_id=link.item_id,
        kb_doc_id=link.kb_doc_id,
        kb_doc_title=doc.title if doc else "",
        relevance_score=link.relevance_score,
        reason=link.reason,
        accepted=link.accepted,
        ai_run_id=link.ai_run_id,
        created_at=link.created_at,
    )


@router.post("/upload", response_model=KBDocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    doc_type: str = Form("document"),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    Upload and ingest a document (.txt, .md, .pdf, .docx).
    Validates file extension and size (up to 10MB). Extracts text content.
    """
    filename = file.filename or "upload.txt"
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # Read file content safely
    contents = await file.read()
    if len(contents) > settings.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.UPLOAD_MAX_BYTES // (1024*1024)}MB",
        )

    doc_text = ""
    # Extract text based on file format
    if ext in (".txt", ".md"):
        try:
            doc_text = contents.decode("utf-8")
        except UnicodeDecodeError:
            doc_text = contents.decode("latin-1", errors="replace")
    elif ext == ".pdf":
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(contents))
            doc_text = "\n\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {e}")
    elif ext == ".docx":
        try:
            import io
            import docx
            doc = docx.Document(io.BytesIO(contents))
            doc_text = "\n".join([p.text for p in doc.paragraphs if p.text])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract text from DOCX: {e}")

    # Save to disk
    os.makedirs("uploads", exist_ok=True)
    save_path = os.path.join("uploads", filename)
    with open(save_path, "wb") as f:
        f.write(contents)

    doc_title = title.strip() if title and title.strip() else Path(filename).stem.replace("_", " ").title()

    data = KBDocumentCreate(
        title=doc_title,
        content=doc_text,
        doc_type=doc_type,
        tags=tags,
    )
    return kb_svc.create_kb_doc(db, data, file_path=save_path)

