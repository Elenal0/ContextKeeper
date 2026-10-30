"""Pydantic schemas for People."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.db.models import Availability


class PersonBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    role: str = Field("", max_length=200)
    availability: Availability = Availability.available
    leave_start: datetime | None = None
    leave_end: datetime | None = None

    @model_validator(mode="after")
    def validate_leave_dates(self) -> "PersonBase":
        if self.leave_start and self.leave_end:
            if self.leave_end < self.leave_start:
                raise ValueError("leave_end must be after leave_start")
        if self.availability == Availability.on_leave and not self.leave_start:
            raise ValueError("leave_start is required when availability is on_leave")
        return self


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: EmailStr | None = None
    role: str | None = Field(None, max_length=200)
    availability: Availability | None = None
    leave_start: datetime | None = None
    leave_end: datetime | None = None


class PersonOut(PersonBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

