"""Status counts, progress math, and final states."""


def test_counts_add_up_and_progress(client):
    r = client.post(
        "/jobs",
        json={
            "title": "T",
            "issued_date": "2026-10-01",
            "recipients": [
                {"name": "Good One"},
                {"name": "Good Two"},
                {"name": ""},
            ],
        },
    )
    body = client.get(f"/jobs/{r.json()['job_id']}").json()
    assert body["total"] == 3
    assert body["succeeded"] + body["failed"] + body["pending"] == body["total"]
    assert body["progress_percent"] == 100.0
    assert body["status"] == "completed_with_errors"


def test_final_status_completed(client):
    r = client.post(
        "/jobs",
        json={"title": "T", "issued_date": "2026-10-01", "recipients": [{"name": "A"}]},
    )
    assert client.get(f"/jobs/{r.json()['job_id']}").json()["status"] == "completed"


def test_final_status_failed(client):
    r = client.post(
        "/jobs", json={"title": "T", "issued_date": "2026-10-01", "recipients": [{"name": ""}]}
    )
    assert client.get(f"/jobs/{r.json()['job_id']}").json()["status"] == "failed"


def test_unknown_job_404(client):
    assert client.get("/jobs/doesnotexist").status_code == 404
