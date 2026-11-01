"""Ensamblaje: único lugar donde cada puerto se conecta con su implementación."""

from dataclasses import dataclass

from redis import Redis

from app.api.gateway.authentication import TokenValidator
from app.business.catalog.references.reference_service import ReferenceService
from app.business.shared.ports import IdempotencyStore
from app.config.settings import Settings
from app.persistence.cache.repeated_requests import RedisIdempotencyStore
from app.persistence.relational.database import build_session_factory
from app.persistence.relational.reference_repository import SqlReferenceRepository


@dataclass(frozen=True)
class Container:
    """Piezas ya armadas que usa la aplicación."""

    settings: Settings
    token_validator: TokenValidator
    idempotency_store: IdempotencyStore
    reference_service: ReferenceService


def build_container(settings: Settings) -> Container:
    """Arma las implementaciones reales a partir de la configuración."""
    session_factory = build_session_factory(settings.mysql_url)
    return Container(
        settings=settings,
        token_validator=TokenValidator(
            secret=settings.jwt_secret,
            algorithms=settings.jwt_algorithms,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        ),
        idempotency_store=RedisIdempotencyStore(
            Redis.from_url(settings.redis_url, decode_responses=True)
        ),
        reference_service=ReferenceService(SqlReferenceRepository(session_factory)),
    )
