"""Startup recovery: pending rows in an interrupted job get processed."""
from datetime import date

from app.models import Certificate, Job
from app.services import processor


def test_recovery_processes_pending(client, tmp_env):
    from app import database as db_module

    session = db_module.SessionLocal()
    job = Job(title="Interrupted", issued_date=date(2026, 10, 1), status="processing")
    session.add(job)
    session.flush()
    session.add_all(
        [
            Certificate(job_id=job.id, recipient_name="Ana", status="pending"),
            Certificate(job_id=job.id, recipient_name="Ben", status="pending"),
        ]
    )
    session.commit()
    job_id = job.id
    session.close()

    processor.recover_interrupted_jobs()

    session = db_module.SessionLocal()
    try:
        refreshed = session.get(Job, job_id)
        assert refreshed.status == "completed"
        assert session.query(Certificate).filter_by(job_id=job_id, status="success").count() == 2
    finally:
        session.close()
