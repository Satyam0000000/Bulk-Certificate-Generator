"""Download behaviour and cross-job isolation."""


def _make_job(client, names):
    r = client.post(
        "/jobs",
        json={"title": "T", "issued_date": "2026-10-01", "recipients": [{"name": n} for n in names]},
    )
    assert r.status_code == 202
    return r.json()["job_id"]


def test_download_success_pdf(client):
    job_id = _make_job(client, ["Asha"])
    cert_id = client.get(f"/jobs/{job_id}/certificates").json()["items"][0]["id"]
    r = client.get(f"/jobs/{job_id}/certificates/{cert_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_download_failed_cert_409(client):
    r = client.post(
        "/jobs",
        json={"title": "T", "issued_date": "2026-10-01", "recipients": [{"name": ""}, {"name": "Ok"}]},
    )
    job_id = r.json()["job_id"]
    items = client.get(f"/jobs/{job_id}/certificates").json()["items"]
    failed = [i for i in items if i["status"] == "failed"][0]
    assert client.get(f"/jobs/{job_id}/certificates/{failed['id']}/download").status_code == 409


def test_download_unknown_cert_404(client):
    job_id = _make_job(client, ["Asha"])
    assert client.get(f"/jobs/{job_id}/certificates/nope/download").status_code == 404


def test_cert_from_another_job_404(client):
    job_a = _make_job(client, ["Alice"])
    job_b = _make_job(client, ["Bob"])
    cert_b = client.get(f"/jobs/{job_b}/certificates").json()["items"][0]["id"]
    assert client.get(f"/jobs/{job_a}/certificates/{cert_b}/download").status_code == 404
