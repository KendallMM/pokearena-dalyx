"""Base de datos de prueba: se crea con las migraciones reales."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.relational.database import build_session_factory

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    # El timeout evita "database is locked" cuando varios hilos escriben a la vez.
    return f"sqlite:///{tmp_path / 'test.db'}?timeout=30"


@pytest.fixture
def session_factory(database_url: str) -> sessionmaker[Session]:
    command.upgrade(alembic_config(database_url), "head")
    return build_session_factory(database_url)
