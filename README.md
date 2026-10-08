# Bulk Certificate Generator

Generate one PDF certificate per recipient from a single template. `POST /jobs` accepts a bulk list, validates each row, processes in the background, and lets the client poll progress and download PDFs. One bad row never blocks the rest.

## Tech stack

FastAPI + Uvicorn, SQLAlchemy + SQLite (WAL, busy timeout), Pydantic v2, ReportLab + bundled Noto Sans, pytest + TestClient, stdlib logging.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
# docs: http://localhost:8000/docs
```

Env vars (all optional): `DATABASE_URL`, `STORAGE_DIR`, `MAX_RECIPIENTS` (default 5000), `PROCESS_SYNC` (true = process inline, used by tests), `WORKERS`, `SQLITE_BUSY_TIMEOUT_MS`.

## Run tests

```bash
pytest -v
```

## API usage

Submit a job (202, processing starts in background):

```bash
curl -s -X POST localhost:8000/jobs -H 'Content-Type: application/json' -d '{
  "title": "Python Bootcamp 2026",
  "issued_date": "2026-10-01",
  "issuer": "Example Academy",
  "recipients": [
    {"name": "Asha Verma", "email": "asha@example.com"},
    {"name": "", "email": "bad"},
    {"foo": "bar"}
  ]
}'
# {"job_id":"...","status":"pending","total":3}
```

Check status:

```bash
curl -s localhost:8000/jobs/<job_id>
```

List certificates (filter `?status=success|failed|pending`, `?limit=&offset=`):

```bash
curl -s 'localhost:8000/jobs/<job_id>/certificates?limit=50&offset=0'
```

Download one PDF:

```bash
curl -o cert.pdf localhost:8000/jobs/<job_id>/certificates/<cert_id>/download
```

Error codes: malformed request 422, unknown job/cert or cross-job cert 404, downloading a failed/pending cert 409, file missing on disk 410.

## Design decisions

- **FastAPI + SQLite, Postgres swap:** zero setup for reviewers; swapping `DATABASE_URL` to Postgres needs no code change. SQLite runs WAL mode with a 30s busy timeout so brief write locks wait instead of failing.
- **Background vs synchronous:** `POST` returns 202 immediately and a thread-pool worker generates PDFs; the client polls `GET /jobs/{id}`. Synchronous would time out on large jobs and block workers. Limit: in-process threads die on restart, mitigated by startup recovery; production answer is Celery + Redis.
- **Two-layer validation:** Pydantic rejects only structural problems (missing title, empty/oversize list → 422). Recipients are `list[dict]` so one junk row like `{"foo":"bar"}` becomes a failed row (`name is required`), not a 422. Row checks: non-empty name, max 100 chars, no control chars, optional email format, email duplicates within the job.
- **Computed counters:** status endpoint uses `GROUP BY status` counts; nothing stored, so concurrent polls can never see drifted numbers.
- **Per-certificate commits:** each PDF commits its row, so progress is live and a crash at #500 keeps #1–499.
- **Atomic file writes:** generator writes to `.tmp` then `os.replace`; a crash never leaves a half-written PDF marked success. Paths are `storage/certificates/{job_id}/{cert_id}.pdf` (IDs only, no user input, no traversal).
- **Restart recovery:** on startup, jobs stuck in `pending`/`processing` have their pending rows re-queued; finished rows are skipped.
- **Duplicate rule:** same email (case-insensitive) twice in one job → later rows fail with `duplicate recipient`. Same payload posted twice creates two separate jobs.

## Limitations and production path

No auth, no rate limiting, single-process thread pool, local disk storage with no retention cleanup, no email delivery, one fixed template. Production: Postgres, Celery + Redis with retries/backoff, S3 storage with lifecycle cleanup, auth + rate limits, metrics, paginated/streaming exports.

## Assumptions

`MAX_RECIPIENTS` 5000; email optional; same name with different emails is allowed; bundled fonts are Latin + Devanagari subsets of Noto Sans (replace with full Noto for wider coverage); missing file on disk returns 410.
