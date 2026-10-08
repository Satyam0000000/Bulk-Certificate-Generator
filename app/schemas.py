"""Pydantic schemas for requests and responses.

Recipients are List[dict] on purpose: one junk row must not 422 the
whole request. Row-level problems are handled by services/validators.py.
"""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    issued_date: date
    issuer: Optional[str] = Field(default=None, max_length=200)
    # Lenient: each row is validated separately in validators.py.
    recipients: list[dict[str, Any]]


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    total: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    succeeded: int
    failed: int
    pending: int
    progress_percent: float
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class CertificateItem(BaseModel):
    id: str
    recipient_name: str
    recipient_email: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    download_url: Optional[str] = None


class CertificateListResponse(BaseModel):
    items: list[CertificateItem]
    limit: int
    offset: int
    total: int
