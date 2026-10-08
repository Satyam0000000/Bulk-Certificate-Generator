"""Central configuration, read from environment variables.

Keep this dumb on purpose: every setting is one env var with a default,
so the behaviour is obvious in an interview.
"""
import os
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'certificates.db'}")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", str(BASE_DIR / "storage" / "certificates"))
    MAX_RECIPIENTS: int = int(os.getenv("MAX_RECIPIENTS", "5000"))
    PROCESS_SYNC: bool = _get_bool("PROCESS_SYNC", False)
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    SQLITE_BUSY_TIMEOUT_MS: int = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "30000"))


settings = Settings()
