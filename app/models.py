"""SQLAlchemy models: one Job has many Certificates."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_job_id", "job_id"),
        Index("ix_certificates_job_id_status", "job_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id"), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
