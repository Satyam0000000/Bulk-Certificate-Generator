"""Shared fixtures: isolated SQLite file, temp storage, sync processing."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database as db_module
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Certificate, Job


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Point the DB, storage, and sync flag at temp locations."""
    db_file = tmp_path / "test.db"
    storage = tmp_path / "storage"
    storage.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "PROCESS_SYNC", True)
    monkeypatch.setattr(settings, "STORAGE_DIR", str(storage))

    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def _pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(db_module, "SessionLocal", TestSession)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield {"engine": test_engine, "Session": TestSession, "storage": storage}
    app.dependency_overrides.clear()


@pytest.fixture()
def client(tmp_env):
    # Clean slate for every test.
    session = tmp_env["Session"]()
    session.query(Certificate).delete()
    session.query(Job).delete()
    session.commit()
    session.close()
    storage = Path(settings.STORAGE_DIR)
    if storage.exists():
        shutil.rmtree(storage)
    storage.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as c:
        yield c
