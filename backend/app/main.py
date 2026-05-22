from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging
from app.core.storage import ensure_bucket_exists
from app.database import engine, Base
from app.models.document import Document  # noqa: F401 — registers ORM mappers
from app.models.users import User  # noqa: F401 — registers ORM mappers
from app.models.log import Log  # noqa: F401 — registers ORM mappers
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ensure_bucket_exists()
    yield


app = FastAPI(title="OCR Platform API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/v1")
app.include_router(documents_router, prefix="/v1")


@app.get("/v1/health", tags=["meta"])
async def health():
    return {"status": "ok"}
