"""Background worker: generate one PDF per pending certificate.

Key rules (see plan.md section 9):
- Each task opens its OWN DB session; never reuse the request session.
- try/except is INSIDE the loop so one failure never stops the job.
- Commit per certificate so progress is live and crashes lose nothing.
- Any unexpected error marks the job failed (never stuck in processing).
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app import database as db_module
from app.config import settings
from app.models import Certificate, Job
from app.services.generator import generate_certificate

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=settings.WORKERS)


def _output_path(job_id: str, cert_id: str) -> Path:
    # IDs only, never user input: no path traversal possible.
    return Path(settings.STORAGE_DIR) / job_id / f"{cert_id}.pdf"


def process_job(job_id: str) -> None:
    session = db_module.SessionLocal()
    try:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("process_job: job not found job_id=%s", job_id)
            return
        if job.status in ("completed", "completed_with_errors", "failed"):
            return

        logger.info("job started job_id=%s", job_id)
        job.status = "processing"
        if job.started_at is None:
            job.started_at = datetime.utcnow()
        session.commit()

        pending = (
            session.query(Certificate)
            .filter(Certificate.job_id == job_id, Certificate.status == "pending")
            .order_by(Certificate.created_at)
            .all()
        )
        issued = job.issued_date.isoformat() if job.issued_date else ""
        for cert in pending:
            try:
                out = _output_path(job_id, cert.id)
                generate_certificate(cert.recipient_name, job.title, issued, job.issuer, out)
                cert.status = "success"
                cert.file_path = f"{job_id}/{cert.id}.pdf"
                cert.error_message = None
            except Exception as exc:  # noqa: BLE001 - one row must not kill the job
                cert.status = "failed"
                cert.error_message = (str(exc) or "generation failed")[:500]
                cert.file_path = None
                logger.warning(
                    "certificate failed job_id=%s certificate_id=%s error=%s",
                    job_id,
                    cert.id,
                    cert.error_message,
                )
            session.commit()

        succeeded = session.query(Certificate).filter_by(job_id=job_id, status="success").count()
        failed = session.query(Certificate).filter_by(job_id=job_id, status="failed").count()
        if failed == 0:
            job.status = "completed"
        elif succeeded == 0:
            job.status = "failed"
        else:
            job.status = "completed_with_errors"
        job.finished_at = datetime.utcnow()
        session.commit()
        logger.info(
            "job finished job_id=%s status=%s succeeded=%d failed=%d",
            job_id,
            job.status,
            succeeded,
            failed,
        )
    except Exception:
        # Last resort: never leave a job stuck in processing.
        try:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                session.commit()
        except Exception:
            session.rollback()
        logger.exception("job crashed job_id=%s", job_id)
    finally:
        session.close()


def submit_job(job_id: str) -> None:
    if settings.PROCESS_SYNC:
        process_job(job_id)
    else:
        executor.submit(process_job, job_id)


def recover_interrupted_jobs() -> None:
    """Re-queue jobs left in pending/processing by a restart (startup hook)."""
    session = db_module.SessionLocal()
    try:
        stuck = session.query(Job).filter(Job.status.in_(["pending", "processing"])).all()
        ids = [job.id for job in stuck]
    finally:
        session.close()
    for job_id in ids:
        logger.info("recovering interrupted job job_id=%s", job_id)
        try:
            submit_job(job_id)
        except Exception:
            logger.exception("recovery submit failed job_id=%s", job_id)
