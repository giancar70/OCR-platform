import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from unittest.mock import patch, MagicMock, AsyncMock

from app.config import settings
from app.database import Base, get_db
from app.models.users import User      # noqa: F401 — register mappers
from app.models.document import Document  # noqa: F401
from app.models.log import Log         # noqa: F401

_TEST_ASYNC_URL = settings.DATABASE_URL.replace("/ocr_db", "/ocr_test_db")
_TEST_SYNC_URL  = _TEST_ASYNC_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
_ADMIN_SYNC_URL = _TEST_SYNC_URL.replace("/ocr_test_db", "/postgres")

_async_engine = create_async_engine(_TEST_ASYNC_URL, poolclass=NullPool)
_TestSession  = async_sessionmaker(_async_engine, expire_on_commit=False)


# ── database lifecycle ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    admin = create_engine(_ADMIN_SYNC_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS ocr_test_db"))
        conn.execute(text("CREATE DATABASE ocr_test_db"))
    admin.dispose()

    sync = create_engine(_TEST_SYNC_URL, poolclass=NullPool)
    Base.metadata.create_all(sync)
    sync.dispose()

    yield

    sync = create_engine(_TEST_SYNC_URL, poolclass=NullPool)
    Base.metadata.drop_all(sync)
    sync.dispose()

    admin = create_engine(_ADMIN_SYNC_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS ocr_test_db"))
    admin.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    sync = create_engine(_TEST_SYNC_URL, poolclass=NullPool)
    with sync.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    sync.dispose()


# ── per-test fixtures ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    async with _TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db

    with patch("app.main.ensure_bucket_exists"), \
         patch("app.api.documents.upload_file"), \
         patch("app.api.documents.delete_file"), \
         patch("app.tasks.ocr.process_document.delay") as mock_delay, \
         patch("app.core.pubsub.publish_async", new_callable=AsyncMock), \
         patch("app.tasks.celery_app.celery_app.control.revoke"):
        mock_delay.return_value = MagicMock(id="test-celery-task-id")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client):
    r = await client.post("/v1/auth/register", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 201
    return r.json()


@pytest_asyncio.fixture
async def auth_headers(client, registered_user):
    r = await client.post("/v1/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
