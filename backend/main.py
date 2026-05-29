from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import settings
from backend.core.database import Base, engine
import backend.models  # noqa: F401 — register ORM models with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="PRism", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
