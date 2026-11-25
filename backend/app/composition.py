"""Ensamblaje: único lugar donde cada puerto se conecta con su implementación."""

from dataclasses import dataclass

from pymongo import MongoClient
from redis import Redis

from app.api.gateway.authentication import TokenIssuer, TokenValidator
from app.api.gateway.google_verifier import GoogleTokenVerifier
from app.business.collection.catalog_browser import CatalogBrowser
from app.business.collection.decks import DeckService
from app.business.collection.initial_collection import InitialCollectionService
from app.business.identity_access.session_service import SessionService
from app.business.identity_access.ports import LoginChallengeStore, PlayerRepository
from app.business.automatic_tasks.matchmaking_job import (
    ExpireSearchesJob,
    MatchmakingJob,
)
from app.business.automatic_tasks.scheduler import Scheduler
from app.business.matchmaking.elo_queue import EloQueue
from app.business.matchmaking.bot import Bot
from app.business.game.matches import MatchService
from app.business.game.match_start import MatchStart
from app.business.automatic_tasks.match_events_job import MatchEventsJob
from app.persistence.relational.match_event_repository import SqlMatchEventRepository
from app.persistence.documents.match_events import MongoMatchHistory
from app.persistence.cache.request_limits import RedisRequestLimiter
from app.persistence.relational.match_repository import SqlMatchRepository
from app.persistence.relational.search_repository import SqlSearchRepository
from app.business.automatic_tasks.thumbnail_job import ThumbnailJob
from app.business.catalog.content.cards.card_availability import CardAvailability
from app.business.catalog.content.cards.card_directory import CardDirectory
from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.thumbnails import ThumbnailPolicy
from app.business.image_processing.image_processor import ImageProcessor
from app.business.shared.ports import IdempotencyStore, RequestLimiter
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
from app.persistence.relational.deck_repository import SqlDeckRepository
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
    catalog_browser: CatalogBrowser | None = None
    deck_service: DeckService | None = None
    players: PlayerRepository | None = None
    login_challenges: LoginChallengeStore | None = None
    token_issuer: TokenIssuer | None = None
    elo_queue: EloQueue | None = None
    match_service: MatchService | None = None
    matchmaking_scheduler: Scheduler | None = None
    search_limiter: RequestLimiter | None = None


def build_container(settings: Settings) -> Container:
    """Arma las implementaciones reales a partir de la configuración."""
    session_factory = build_session_factory(settings.mysql_url)
    reference_service = ReferenceService(SqlReferenceRepository(session_factory))
    documents = MongoClient(settings.mongo_url)[settings.mongo_database]
    image_store = MongoImageStore(documents["images"])
    pending_events = SqlMatchEventRepository(session_factory)
    events_job = MatchEventsJob(
        pending_events,
        MongoMatchHistory(documents["match_events"]),
        settings.match_events_interval_seconds,
    )
    clock = SystemClock()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    players = SqlPlayerRepository(session_factory)
    card_repository = SqlCardRepository(session_factory)
    collection_repository = SqlCollectionRepository(session_factory)
    collections = InitialCollectionService(
        transactions=SqlTransactionManager(session_factory),
        deliveries=players,
        cards=CardAvailability(card_repository),
        collection=collection_repository,
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
    card_search_repository = SqlCardSearchRepository(session_factory)
    card_search_service = CardSearchService(
        references=reference_service,
        cards=card_search_repository,
        image_store=image_store,
    )
    scheduler = (
        Scheduler(
            [
                ThumbnailJob(card_service, "card_thumbnails"),
                ThumbnailJob(location_service, "location_thumbnails"),
                collections,
                events_job,
            ],
            settings.thumbnail_interval_seconds,
            job_intervals={events_job.name: settings.match_events_interval_seconds},
        )
        if settings.scheduler_enabled
        else None
    )
    deck_service = DeckService(
        SqlDeckRepository(session_factory),
        CardDirectory(card_search_repository),
        collection_repository,
    )
    searches = SqlSearchRepository(session_factory)
    match_service = MatchService(
        SqlMatchRepository(session_factory),
        players,
        searches,
        MatchStart(
            deck_service,
            card_service,
            location_service,
            clock,
            SystemRandomSource(),
        ),
        pending_events,
        reference_service,
    )
    elo_queue = EloQueue(
        searches,
        deck_service,
        match_service,
        players,
        SqlCubeRepository(),
        SqlTransactionManager(session_factory),
        clock,
        bot=Bot(CardAvailability(card_repository), SystemRandomSource()),
        inactivity_seconds=settings.search_inactivity_seconds,
    )
    return Container(
        elo_queue=elo_queue,
        match_service=match_service,
        matchmaking_scheduler=(
            Scheduler(
                [
                    ExpireSearchesJob(elo_queue),
                    MatchmakingJob(elo_queue),
                ],
                settings.matchmaking_interval_seconds,
                job_intervals={
                    ExpireSearchesJob.name: settings.search_expiry_interval_seconds
                },
            )
            if settings.scheduler_enabled
            else None
        ),
        search_limiter=RedisRequestLimiter(
            redis_client,
            settings.search_request_limit,
            settings.search_request_window_seconds,
        ),
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
        catalog_browser=CatalogBrowser(card_search_service, collection_repository),
        deck_service=deck_service,
        players=players,
        login_challenges=RedisLoginChallengeStore(redis_client),
        token_issuer=TokenIssuer(
            settings.jwt_secret,
            settings.jwt_issuer,
            settings.jwt_audience,
            settings.jwt_expiration_minutes,
        ),
    )
