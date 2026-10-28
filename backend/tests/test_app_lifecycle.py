import dataclasses

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import ConfigError, Settings, load_settings
from app.main import create_app
from tests.api import post_card
from tests.helpers import CURSOR_SECRET, JWT_SECRET, auth


async def test_lifespan_starts_worker_and_processes_without_background(
    container, settings
):
    """Arranque real: el ciclo del worker procesa la imagen por sí solo."""
    import asyncio

    live = dataclasses.replace(
        settings, run_image_worker=True, image_worker_poll_seconds=0.05
    )
    app = create_app(
        live,
        session_factory=container.session_factory,
        mongo_database=container.card_images._collection.database,
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            from fastapi import BackgroundTasks

            BackgroundTasks.add_task, original = (
                lambda self, *a, **k: None
            ), BackgroundTasks.add_task
            try:
                code = (await post_card(client)).json()["code"]
            finally:
                BackgroundTasks.add_task = original
            for _ in range(100):
                s = (
                    await client.get(f"/admin/cartas/{code}/estado", headers=auth())
                ).json()
                if s["status"] == "READY":
                    break
                await asyncio.sleep(0.05)
            assert s["status"] == "READY"


async def test_health_endpoint(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


def env(**overrides):
    base = {
        "DATABASE_URL": "mysql+aiomysql://u:p@db/x",
        "MONGO_URL": "mongodb://mongo:27017",
        "JWT_SECRET": JWT_SECRET,
        "CURSOR_SECRET": CURSOR_SECRET,
    }
    base.update(overrides)
    return base


def test_settings_from_env():
    s = load_settings(env(JWT_ISSUER="poke"))
    assert (
        s.jwt_issuer == "poke" and s.jwt_algorithms == ("HS256",) and s.run_image_worker
    )


@pytest.mark.parametrize(
    "missing", ["DATABASE_URL", "MONGO_URL", "JWT_SECRET", "CURSOR_SECRET"]
)
def test_missing_required_env_fails(missing):
    e = env()
    del e[missing]
    with pytest.raises(ConfigError):
        load_settings(e)


def test_weak_or_unsafe_settings_rejected():
    with pytest.raises(ConfigError):
        load_settings(env(JWT_SECRET="corta"))
    with pytest.raises(ConfigError):
        load_settings(env(CURSOR_SECRET="corta"))
    with pytest.raises(ConfigError):
        load_settings(env(JWT_ALGORITHMS="HS256,none"))
    with pytest.raises(ConfigError):
        Settings("a", "b", "c", "x" * 32, "y" * 31)
