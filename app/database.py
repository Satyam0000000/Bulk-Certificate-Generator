"""Engine, sessions, and the FastAPI DB dependency."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# check_same_thread=False is required because background threads share the engine.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)


# SQLite only: WAL lets readers and one writer coexist; busy_timeout makes
# brief write locks wait instead of raising "database is locked".
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute(f"PRAGMA busy_timeout={settings.SQLITE_BUSY_TIMEOUT_MS};")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
