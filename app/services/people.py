"""People service — CRUD operations."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Availability, Person
from app.schemas.people import PersonCreate, PersonUpdate


def list_people(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[Person]:
    q = db.query(Person)
    if not include_inactive:
        q = q.filter(Person.is_active.is_(True))
    return q.offset(skip).limit(limit).all()


def get_person(db: Session, person_id: int) -> Person:
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail=f"Person {person_id} not found")
    return person


def create_person(db: Session, data: PersonCreate) -> Person:
    # Check unique email
    existing = db.query(Person).filter(Person.email == str(data.email)).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A person with email '{data.email}' already exists",
        )
    person = Person(
        name=data.name,
        email=str(data.email),
        role=data.role,
        availability=data.availability,
        leave_start=data.leave_start,
        leave_end=data.leave_end,
        is_active=True,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def update_person(db: Session, person_id: int, data: PersonUpdate) -> Person:
    person = get_person(db, person_id)
    updates = data.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        new_email = str(updates["email"])
        existing = (
            db.query(Person)
            .filter(Person.email == new_email, Person.id != person_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Email '{new_email}' is already taken",
            )
        updates["email"] = new_email
    for field, value in updates.items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    return person


def delete_person(db: Session, person_id: int) -> None:
    """Soft delete: set is_active=False."""
    person = get_person(db, person_id)
    person.is_active = False
    db.commit()


def get_available_people(db: Session) -> list[Person]:
    """Return active people who are not on leave."""
    return (
        db.query(Person)
        .filter(
            Person.is_active.is_(True),
            Person.availability != Availability.on_leave,
        )
        .all()
    )
