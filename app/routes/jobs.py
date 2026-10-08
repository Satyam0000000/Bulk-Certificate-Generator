"""Job endpoints: create, status, list certificates, download."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Certificate, Job
from app.schemas import (
    CertificateItem,
    CertificateListResponse,
    CreateJobRequest,
    JobCreatedResponse,
    JobStatusResponse,
)
from app.services.validators import validate_recipient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreatedResponse, status_code=202)
def create_job(payload: CreateJobRequest, db: Session = Depends(get_db)):
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title must not be empty")

    recipients = payload.recipients or []
    if len(recipients) == 0:
        raise HTTPException(status_code=422, detail="recipients must contain at least 1 item")
    if len(recipients) > settings.MAX_RECIPIENTS:
        raise HTTPException(
            status_code=422,
            detail=f"recipients must contain at most {settings.MAX_RECIPIENTS} items",
        )

    issuer = payload.issuer.strip() if isinstance(payload.issuer, str) and payload.issuer.strip() else None

    job = Job(title=title, issued_date=payload.issued_date, issuer=issuer, status="pending")
    db.add(job)
    db.flush()  # assigns job.id before we insert certificates

    seen_emails: set[str] = set()
    rows: list[Certificate] = []
    for raw in recipients:
        name, email, error = validate_recipient(raw, seen_emails)
        rows.append(
            Certificate(
                job_id=job.id,
                recipient_name=name,
                recipient_email=email,
                status="failed" if error else "pending",
                error_message=error,
            )
        )
    db.add_all(rows)
    db.commit()

    # Fire-and-forget: the worker opens its OWN session (never this one).
    from app.services import processor

    try:
        processor.submit_job(job.id)
    except Exception:
        logger.exception("failed to submit job_id=%s", job.id)

    return JobCreatedResponse(job_id=job.id, status=job.status, total=len(rows))


def _counts(db: Session, job_id: str) -> dict[str, int]:
    result = (
        db.query(Certificate.status, func.count(Certificate.id))
        .filter(Certificate.job_id == job_id)
        .group_by(Certificate.status)
        .all()
    )
    counts = {"pending": 0, "success": 0, "failed": 0}
    for status, count in result:
        if status in counts:
            counts[status] = count
    return counts


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    counts = _counts(db, job_id)
    total = counts["pending"] + counts["success"] + counts["failed"]
    done = counts["success"] + counts["failed"]
    progress = round(done / total * 100, 1) if total else 0.0
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=total,
        succeeded=counts["success"],
        failed=counts["failed"],
        pending=counts["pending"],
        progress_percent=progress,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("/{job_id}/certificates", response_model=CertificateListResponse)
def list_certificates(
    job_id: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if status is not None and status not in ("pending", "success", "failed"):
        raise HTTPException(status_code=422, detail="invalid status filter")

    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status is not None:
        query = query.filter(Certificate.status == status)
    total = query.count()
    rows = query.order_by(Certificate.created_at).offset(offset).limit(limit).all()

    items = [
        CertificateItem(
            id=row.id,
            recipient_name=row.recipient_name,
            recipient_email=row.recipient_email,
            status=row.status,
            error_message=row.error_message,
            download_url=f"/jobs/{job_id}/certificates/{row.id}/download"
            if row.status == "success"
            else None,
        )
        for row in rows
    ]
    return CertificateListResponse(items=items, limit=limit, offset=offset, total=total)


@router.get("/{job_id}/certificates/{cert_id}/download")
def download_certificate(job_id: str, cert_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    cert = db.get(Certificate, cert_id)
    if cert is None or cert.job_id != job_id:
        raise HTTPException(status_code=404, detail="certificate not found")
    if cert.status != "success":
        raise HTTPException(status_code=409, detail=f"certificate is {cert.status}")

    # Resolve inside STORAGE_DIR only; file_path uses IDs, never user input.
    base = Path(settings.STORAGE_DIR).resolve()
    rel = cert.file_path or f"{job_id}/{cert.id}.pdf"
    path = (base / rel).resolve()
    if base not in path.parents and path != base:
        raise HTTPException(status_code=404, detail="certificate not found")
    if not path.is_file():
        logger.error("missing file on disk job_id=%s certificate_id=%s path=%s", job_id, cert.id, path)
        raise HTTPException(status_code=410, detail="file missing on disk")
    return FileResponse(str(path), media_type="application/pdf", filename=f"certificate-{cert.id[:8]}.pdf")
