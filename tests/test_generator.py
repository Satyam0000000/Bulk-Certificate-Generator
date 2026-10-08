"""Direct generator tests: file validity, long and Unicode names."""
from pathlib import Path

from app.config import settings
from app.services.generator import generate_certificate


def test_pdf_header_and_nonempty(tmp_path):
    out = tmp_path / "cert.pdf"
    generate_certificate("Asha Verma", "Python Bootcamp", "2026-10-01", "Academy", out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:5] == b"%PDF-"


def test_long_name_does_not_crash(tmp_path):
    out = tmp_path / "long.pdf"
    generate_certificate("A" * 100, "Course", "2026-10-01", None, out)
    assert out.read_bytes()[:5] == b"%PDF-"


def test_unicode_name(tmp_path):
    out = tmp_path / "uni.pdf"
    generate_certificate("José François आशा", "Course", "2026-10-01", None, out)
    assert out.read_bytes()[:5] == b"%PDF-"


def test_output_inside_storage_dir(client):
    r = client.post(
        "/jobs",
        json={"title": "T", "issued_date": "2026-10-01", "recipients": [{"name": "Zed"}]},
    )
    job_id = r.json()["job_id"]
    items = client.get(f"/jobs/{job_id}/certificates").json()["items"]
    assert items[0]["status"] == "success"
    base = Path(settings.STORAGE_DIR).resolve()
    expected = (base / job_id / f"{items[0]['id']}.pdf").resolve()
    assert expected.is_file()
    assert base in expected.parents
