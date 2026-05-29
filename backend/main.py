from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import settings
from backend.core.database import Base, engine
import backend.models  # noqa: F401 — register ORM models with Base.metadata

from backend.api.projects import router as projects_router
from backend.api.reviews import router as reviews_router
from backend.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield


app = FastAPI(title="PRism", version="0.1.0", lifespan=lifespan)
app.include_router(projects_router)
app.include_router(reviews_router)


@app.get("/health")
def health():
    return {"status": "ok"}
