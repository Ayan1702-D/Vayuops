"""Consistent API errors."""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Build an HTTP exception carrying the shared error shape."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
