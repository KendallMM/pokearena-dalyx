"""Piezas compartidas por las pruebas."""

from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.gateway.authentication import TokenValidator
from app.api.gateway.errors import ADMIN_ERROR_RESPONSES
from app.api.gateway.idempotency import IdempotencyContext, idempotency_context
from app.composition import Container
from app.config.settings import Settings
from app.main import create_app
from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.image_processing.image_processor import ImageProcessor
from tests.fakes import (
    FakeCardRepository,
    FakeClock,
    FakeImageStore,
    FakeReferenceRepository,
    InMemoryIdempotencyStore,
)

SECRET = "clave-de-prueba-de-al-menos-32-caracteres!!"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        mysql_url="mysql+pymysql://u:p@localhost/db",
        mongo_url="mongodb://localhost:27017",
        redis_url="redis://localhost:6379/0",
        jwt_secret=SECRET,
    )


@pytest.fixture
def make_token(settings: Settings) -> Callable[..., str]:
    def _make(role: str | None = "content_admin", **overrides: object) -> str:
        claims: dict[str, object] = {
            "sub": "user-1",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        if role is not None:
            claims["role"] = role
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, SECRET, algorithm="HS256")

    return _make


@pytest.fixture
def validator(settings: Settings) -> TokenValidator:
    return TokenValidator(
        SECRET, settings.jwt_algorithms, settings.jwt_issuer, settings.jwt_audience
    )


@pytest.fixture
def reference_repository() -> FakeReferenceRepository:
    return FakeReferenceRepository()


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def image_store(events: list[str]) -> FakeImageStore:
    return FakeImageStore(events)


@pytest.fixture
def card_repository(events: list[str]) -> FakeCardRepository:
    return FakeCardRepository(events)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def card_service(
    reference_repository: FakeReferenceRepository,
    image_store: FakeImageStore,
    card_repository: FakeCardRepository,
    clock: FakeClock,
) -> CardService:
    return CardService(
        references=ReferenceService(reference_repository),
        image_processor=ImageProcessor(),
        image_store=image_store,
        cards=card_repository,
        clock=clock,
    )


@pytest.fixture
def store() -> InMemoryIdempotencyStore:
    return InMemoryIdempotencyStore()


class _Payload(BaseModel):
    name: str = Field(min_length=1)
    cost: int = Field(ge=0, le=10)


@pytest.fixture
def handler_calls() -> list[str]:
    return []


@pytest.fixture
def client(
    settings: Settings,
    validator: TokenValidator,
    store: InMemoryIdempotencyStore,
    reference_repository: FakeReferenceRepository,
    card_service: CardService,
    handler_calls: list[str],
) -> TestClient:
    """Aplicación real con un endpoint de prueba protegido por el gateway."""
    app = create_app(
        Container(
            settings,
            validator,
            store,
            ReferenceService(reference_repository),
            card_service,
        )
    )

    @app.post("/test/things", status_code=202, responses=ADMIN_ERROR_RESPONSES)
    def create_thing(
        payload: _Payload, ctx: IdempotencyContext = Depends(idempotency_context)
    ):
        handler_calls.append(payload.name)
        return ctx.respond(202, {"id": len(handler_calls), "name": payload.name})

    @app.get("/test/boom")
    def boom() -> None:
        raise RuntimeError("fallo interno con datos sensibles")

    return TestClient(app, raise_server_exceptions=False)
