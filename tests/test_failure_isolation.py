"""One generator crash must not stop the rest of the job."""
from app.services import generator as gen_module
from app.services import processor


def test_individual_failure_isolated(client, tmp_env, monkeypatch):
    real_generate = gen_module.generate_certificate

    def flaky(name, title, issued, issuer, out):
        if name == "Boom":
            raise RuntimeError("printer jam")
        return real_generate(name, title, issued, issuer, out)

    monkeypatch.setattr(gen_module, "generate_certificate", flaky)
    monkeypatch.setattr(processor, "generate_certificate", flaky)

    r = client.post(
        "/jobs",
        json={
            "title": "T",
            "issued_date": "2026-10-01",
            "recipients": [{"name": "Boom"}, {"name": "Fine"}],
        },
    )
    job_id = r.json()["job_id"]
    body = client.get(f"/jobs/{job_id}").json()
    assert body["status"] == "completed_with_errors"
    assert body["succeeded"] == 1
    assert body["failed"] == 1

    items = client.get(f"/jobs/{job_id}/certificates").json()["items"]
    boom = [i for i in items if i["recipient_name"] == "Boom"][0]
    assert boom["status"] == "failed"
    assert "printer jam" in boom["error_message"]
