"""People router — manage team members and their availability."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.people import PersonCreate, PersonOut, PersonUpdate
from app.services import people as people_svc

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    return people_svc.list_people(db, skip=skip, limit=limit, include_inactive=include_inactive)


@router.post("", response_model=PersonOut, status_code=201)
def create_person(data: PersonCreate, db: Session = Depends(get_db)):
    try:
        return people_svc.create_person(db, data)
    except people_svc.DuplicateEmail as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db)):
    try:
        return people_svc.get_person(db, person_id)
    except people_svc.PersonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{person_id}", response_model=PersonOut)
def update_person(person_id: int, data: PersonUpdate, db: Session = Depends(get_db)):
    try:
        return people_svc.update_person(db, person_id, data)
    except people_svc.PersonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except people_svc.DuplicateEmail as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    try:
        people_svc.delete_person(db, person_id)
    except people_svc.PersonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

