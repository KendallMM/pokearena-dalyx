"""Ensamblaje: único lugar donde cada puerto se conecta con su implementación."""

from dataclasses import dataclass

from pymongo import MongoClient
from redis import Redis

from app.api.gateway.authentication import TokenIssuer, TokenValidator
from app.api.gateway.google_verifier import GoogleTokenVerifier
from app.business.collection.initial_collection import InitialCollectionService
from app.business.identity_access.session_service import SessionService
from app.business.identity_access.ports import LoginChallengeStore, PlayerRepository
from app.business.automatic_tasks.scheduler import Scheduler
from app.business.automatic_tasks.thumbnail_job import ThumbnailJob
from app.business.catalog.content.cards.card_availability import CardAvailability
from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.thumbnails import ThumbnailPolicy
from app.business.image_processing.image_processor import ImageProcessor
from app.business.shared.ports import IdempotencyStore
from app.config.settings import Settings
from app.persistence.cache.repeated_requests import RedisIdempotencyStore
from app.persistence.cache.login_challenges import RedisLoginChallengeStore
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.integrations.system_random import SystemRandomSource
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.card_search_repository import SqlCardSearchRepository
from app.persistence.relational.database import build_session_factory
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.reference_repository import SqlReferenceRepository
from app.persistence.relational.player_repository import SqlPlayerRepository
from app.persistence.relational.collection_repository import SqlCollectionRepository
from app.persistence.relational.cube_repository import SqlCubeRepository
from app.persistence.relational.transactions import SqlTransactionManager


@dataclass(frozen=True)
class Container:
    """Piezas ya armadas que usa la aplicación."""

    settings: Settings
    token_validator: TokenValidator
    idempotency_store: IdempotencyStore
    reference_service: ReferenceService
    card_service: CardService
    location_service: LocationService
    card_search_service: CardSearchService
    scheduler: Scheduler | None = None
    session_service: SessionService | None = None
    initial_collection_service: InitialCollectionService | None = None
    players: PlayerRepository | None = None
    login_challenges: LoginChallengeStore | None = None
    token_issuer: TokenIssuer | None = None


def build_container(settings: Settings) -> Container:
    """Arma las implementaciones reales a partir de la configuración."""
    session_factory = build_session_factory(settings.mysql_url)
    reference_service = ReferenceService(SqlReferenceRepository(session_factory))
    images = MongoClient(settings.mongo_url)[settings.mongo_database]["images"]
    image_store = MongoImageStore(images)
    clock = SystemClock()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    players = SqlPlayerRepository(session_factory)
    card_repository = SqlCardRepository(session_factory)
    collections = InitialCollectionService(
        transactions=SqlTransactionManager(session_factory),
        deliveries=players,
        cards=CardAvailability(card_repository),
        collection=SqlCollectionRepository(),
        cubes=SqlCubeRepository(),
        clock=clock,
        random=SystemRandomSource(),
        retry_seconds=settings.initial_collection_retry_seconds,
    )
    thumbnail_policy = ThumbnailPolicy(
        batch_size=settings.thumbnail_batch_size,
        lease_seconds=settings.thumbnail_lease_seconds,
        retry_delay_seconds=settings.thumbnail_retry_delay_seconds,
    )
    card_service = CardService(
        references=reference_service,
        image_processor=ImageProcessor(),
        image_store=image_store,
        cards=card_repository,
        clock=clock,
        thumbnail_policy=thumbnail_policy,
    )
    location_service = LocationService(
        references=reference_service,
        image_processor=ImageProcessor(),
        image_store=image_store,
        locations=SqlLocationRepository(session_factory),
        clock=clock,
        thumbnail_policy=thumbnail_policy,
    )
    card_search_service = CardSearchService(
        references=reference_service,
        cards=SqlCardSearchRepository(session_factory),
        image_store=image_store,
    )
    scheduler = (
        Scheduler(
            [
                ThumbnailJob(card_service, "card_thumbnails"),
                ThumbnailJob(location_service, "location_thumbnails"),
                collections,
            ],
            settings.thumbnail_interval_seconds,
        )
        if settings.scheduler_enabled
        else None
    )
    return Container(
        settings=settings,
        token_validator=TokenValidator(
            secret=settings.jwt_secret,
            algorithms=settings.jwt_algorithms,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        ),
        idempotency_store=RedisIdempotencyStore(redis_client),
        reference_service=reference_service,
        card_service=card_service,
        location_service=location_service,
        card_search_service=card_search_service,
        scheduler=scheduler,
        session_service=SessionService(
            GoogleTokenVerifier(
                settings.google_client_id, settings.google_timeout_seconds
            ),
            players,
        ),
        initial_collection_service=collections,
        players=players,
        login_challenges=RedisLoginChallengeStore(redis_client),
        token_issuer=TokenIssuer(
            settings.jwt_secret,
            settings.jwt_issuer,
            settings.jwt_audience,
            settings.jwt_expiration_minutes,
        ),
    )
