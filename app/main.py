"""App entrypoint: create tables, mount routes, recover interrupted jobs."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not exist yet.
    Base.metadata.create_all(bind=engine)
    # Restart recovery: re-queue jobs left in pending/processing by a crash.
    try:
        from app.services import processor

        processor.recover_interrupted_jobs()
    except Exception:
        logger.exception("startup recovery failed")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from app.routes.jobs import router as jobs_router

    app.include_router(jobs_router)

    return app


app = create_app()
