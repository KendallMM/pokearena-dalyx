import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.models.ubicacion_model  # noqa: F401  (registra sus tablas)
from app.database import Settings, create_engine, create_session_factory, init_db
from app.main import build_container, create_app
from app.models.carta_model import Base
from tests.helpers import CURSOR_SECRET, JWT_SECRET


def _database_url(tmp_path: Path) -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="unused",
        mongo_url="unused",
        mongo_db_name="test",
        jwt_secret=JWT_SECRET,
        cursor_secret=CURSOR_SECRET,
        run_image_worker=False,
        image_max_attempts=3,
        image_retry_base_seconds=0,
    )


@pytest_asyncio.fixture
async def engine(tmp_path):
    engine = create_engine(_database_url(tmp_path))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
def is_mysql(engine) -> bool:
    return engine.dialect.name in ("mysql", "mariadb")


@pytest.fixture
def mongo_db():
    return AsyncMongoMockClient()["pokearena_test"]


@pytest_asyncio.fixture
async def container(engine, mongo_db, settings):
    factory = create_session_factory(engine)
    return build_container(settings, factory, mongo_db)


@pytest_asyncio.fixture
async def app(container):
    application = create_app(container.settings)
    application.state.container = container
    return application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client


@pytest.fixture
def no_background(monkeypatch):
    """Evita que la imagen se procese sola tras la respuesta (la pone en cola)."""
    from fastapi import BackgroundTasks

    monkeypatch.setattr(BackgroundTasks, "add_task", lambda self, *a, **k: None)
