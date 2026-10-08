"""Request-level 422s and per-row failures (request still accepted)."""
from app.config import settings


def _base(recipients):
    return {"title": "Course", "issued_date": "2026-10-01", "recipients": recipients}


def test_empty_recipients_422(client):
    r = client.post("/jobs", json=_base([]))
    assert r.status_code == 422


def test_missing_title_422(client):
    payload = {"issued_date": "2026-10-01", "recipients": [{"name": "A"}]}
    r = client.post("/jobs", json=payload)
    assert r.status_code == 422


def test_over_max_recipients_422(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_RECIPIENTS", 2)
    r = client.post("/jobs", json=_base([{"name": "A"}, {"name": "B"}, {"name": "C"}]))
    assert r.status_code == 422


def test_bad_email_row_failed_others_succeed(client):
    r = client.post(
        "/jobs",
        json=_base([{"name": "Good", "email": "good@example.com"}, {"name": "Bad", "email": "not-an-email"}]),
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    status = client.get(f"/jobs/{job_id}").json()
    assert status["succeeded"] == 1
    assert status["failed"] == 1


def test_empty_name_failed(client):
    r = client.post("/jobs", json=_base([{"name": "   "}]))
    assert r.status_code == 202
    items = client.get(f"/jobs/{r.json()['job_id']}/certificates").json()["items"]
    assert items[0]["status"] == "failed"


def test_junk_row_failed(client):
    r = client.post("/jobs", json=_base([{"foo": "bar"}, {"name": "Fine"}]))
    assert r.status_code == 202
    items = client.get(f"/jobs/{r.json()['job_id']}/certificates").json()["items"]
    by_status = {i["recipient_name"]: i for i in items}
    junk = [i for i in items if i["status"] == "failed"][0]
    assert "name is required" in junk["error_message"]


def test_duplicate_email_flagged(client):
    r = client.post(
        "/jobs",
        json=_base(
            [{"name": "A", "email": "dup@example.com"}, {"name": "B", "email": "DUP@example.com"}]
        ),
    )
    assert r.status_code == 202
    items = client.get(f"/jobs/{r.json()['job_id']}/certificates").json()["items"]
    assert items[0]["status"] == "success"
    assert items[1]["status"] == "failed"
    assert "duplicate" in items[1]["error_message"]


def test_all_invalid_job_ends_failed(client):
    r = client.post("/jobs", json=_base([{"name": ""}, {"foo": "bar"}]))
    assert r.status_code == 202
    status = client.get(f"/jobs/{r.json()['job_id']}").json()
    assert status["status"] == "failed"
    assert status["failed"] == 2
