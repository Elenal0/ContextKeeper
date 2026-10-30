"""Common schema utilities and error envelope."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str = ""


class ErrorResponse(BaseModel):
    error: ErrorEnvelope


class SuccessResponse(BaseModel):
    message: str
    data: Any = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int

