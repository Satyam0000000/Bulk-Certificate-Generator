"""Create-job happy path."""


def test_create_job_returns_202_with_rows(client, tmp_env):
    payload = {
        "title": "Python Bootcamp 2026",
        "issued_date": "2026-10-01",
        "issuer": "Example Academy",
        "recipients": [
            {"name": "Asha Verma", "email": "asha@example.com"},
            {"name": "Rohan Singh", "email": "rohan@example.com"},
        ],
    }
    r = client.post("/jobs", json=payload)
    assert r.status_code == 202
    body = r.json()
    assert body["total"] == 2
    assert body["job_id"]

    from app.models import Certificate, Job

    session = tmp_env["Session"]()
    try:
        assert session.get(Job, body["job_id"]) is not None
        rows = session.query(Certificate).filter_by(job_id=body["job_id"]).all()
        assert len(rows) == 2
    finally:
        session.close()
