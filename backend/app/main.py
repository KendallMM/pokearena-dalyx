"""Punto de entrada: ``uvicorn app.main:create_app --factory``.

Arma los componentes, registra el manejo de errores, las rutas y el ciclo que
procesa las imágenes pendientes.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import (
    CreationFlow,
    ImageJobRepository,
    ImageStore,
    Settings,
    create_engine,
    create_session_factory,
    init_db,
    load_settings,
    make_thumbnail,
)
from app.engine.ability_engine import (
    CARD_IMAGE_SPEC,
    CONTENT_TYPE_BY_FORMAT,
    LOCATION_IMAGE_SPEC,
    STATUS_READY,
    STATUS_RETRY_IMAGE,
    DomainError,
    EvolutionRuleError,
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    ImageRequirementError,
    InvalidAbilityError,
    InvalidCursorError,
    InvalidFieldError,
    NotAuthenticatedError,
    NotFoundError,
    PermissionDeniedError,
    StorageUnavailableError,
    TokenExpiredError,
)
from app.models.carta_model import (
    ENTITY_CARD,
    ENTITY_LOCATION_VERSION,
)
from app.routers import cartas, ubicaciones
from app.routers.cartas import (
    CardRepository,
    CardSearchService,
    CardService,
)
from app.routers.ubicaciones import (
    GameLocationRepository,
    GameLocationService,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Componentes de la aplicación
# ======================================================================


@dataclass
class Container:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    card_images: ImageStore
    location_images: ImageStore
    card_service: CardService
    location_service: GameLocationService
    search_service: CardSearchService
    image_processing: "ImageProcessingService"


def build_container(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    mongo_database,
) -> Container:
    card_images = ImageStore(mongo_database["card_images"])
    location_images = ImageStore(mongo_database["location_images"])
    ttl = settings.temporary_image_ttl_seconds
    return Container(
        settings=settings,
        session_factory=session_factory,
        card_images=card_images,
        location_images=location_images,
        card_service=CardService(
            session_factory,
            card_images,
            CreationFlow(session_factory, card_images, ttl),
        ),
        location_service=GameLocationService(
            session_factory, CreationFlow(session_factory, location_images, ttl)
        ),
        search_service=CardSearchService(session_factory, settings.cursor_secret),
        image_processing=ImageProcessingService(
            session_factory, card_images, location_images, settings
        ),
    )


# ======================================================================
# Procesamiento de imágenes pendientes
# ======================================================================


class ImageProcessingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        card_images: ImageStore,
        location_images: ImageStore,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._stores = {
            ENTITY_CARD: (card_images, CARD_IMAGE_SPEC),
            ENTITY_LOCATION_VERSION: (location_images, LOCATION_IMAGE_SPEC),
        }

    async def run_due_jobs(self) -> int:
        """Procesa los trabajos que ya les toca; devuelve cuántos reclamó."""
        async with self._session_factory() as session:
            ids = await ImageJobRepository(session).due_job_ids()
        processed = 0
        for job_id in ids:
            if await self.process_job(job_id):
                processed += 1
        return processed

    async def process_job(self, job_id: int) -> bool:
        """Reclama y procesa un trabajo. ``False`` si otro worker ya lo tomó."""
        async with self._session_factory() as session, session.begin():
            repository = ImageJobRepository(session)
            if not await repository.claim(job_id, self._settings.image_lock_seconds):
                return False
            job = await repository.get(job_id)
            attempts = job.attempts
            snapshot = (job.entity_type, job.entity_id, job.image_ref)

        entity_type, entity_id, image_ref = snapshot
        try:
            if attempts > self._settings.image_max_attempts:
                raise RuntimeError("Se superó el máximo de intentos.")
            await self._build_thumbnail(entity_type, image_ref)
            await self._finish(job_id, entity_type, entity_id)
        except Exception as exc:  # cualquier fallo se reintenta con espera
            logger.warning("Fallo procesando imagen (trabajo %s): %s", job_id, exc)
            await self._register_failure(
                job_id, entity_type, entity_id, attempts, str(exc) or type(exc).__name__
            )
        return True

    async def _build_thumbnail(self, entity_type: str, image_ref: str) -> None:
        store, spec = self._stores[entity_type]
        document = await store.get(image_ref)
        if not document or not document.get("original"):
            raise RuntimeError("No se encontró la imagen original.")
        thumbnail, image_format = await asyncio.to_thread(
            make_thumbnail, bytes(document["original"]), spec.thumbnail_size
        )
        await store.set_thumbnail(
            image_ref, thumbnail, CONTENT_TYPE_BY_FORMAT[image_format.upper()]
        )
        if not await store.has_both(image_ref):
            raise RuntimeError("La imagen y su miniatura no quedaron guardadas.")

    async def _finish(self, job_id: int, entity_type: str, entity_id: int) -> None:
        async with self._session_factory() as session, session.begin():
            await self._set_entity_status(session, entity_type, entity_id, STATUS_READY)
            await ImageJobRepository(session).mark_done(job_id)

    async def _register_failure(
        self,
        job_id: int,
        entity_type: str,
        entity_id: int,
        attempts: int,
        error: str,
    ) -> None:
        final = attempts >= self._settings.image_max_attempts
        delay = self._settings.image_retry_base_seconds * 2 ** max(attempts - 1, 0)
        async with self._session_factory() as session, session.begin():
            await self._set_entity_status(
                session, entity_type, entity_id, STATUS_RETRY_IMAGE
            )
            await ImageJobRepository(session).mark_failed_attempt(
                job_id, error, final=final, retry_in_seconds=delay
            )

    @staticmethod
    async def _set_entity_status(
        session: AsyncSession, entity_type: str, entity_id: int, status: str
    ) -> None:
        if entity_type == ENTITY_CARD:
            await CardRepository(session).set_status(entity_id, status)
        else:
            await GameLocationRepository(session).set_version_status(entity_id, status)


# ======================================================================
# Ciclo del worker de imágenes
# ======================================================================


async def run_image_worker(
    service: ImageProcessingService, interval_seconds: float, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        try:
            await service.run_due_jobs()
        except Exception:  # el ciclo nunca debe morir por un error aislado
            logger.exception("Error en el ciclo del worker de imágenes")
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)


# ======================================================================
# Manejo de errores
# ======================================================================


STATUS_BY_CODE: dict[str, int] = {
    NotAuthenticatedError.code: 401,
    TokenExpiredError.code: 401,
    PermissionDeniedError.code: 403,
    InvalidFieldError.code: 400,
    ImageRequirementError.code: 400,
    InvalidAbilityError.code: 400,
    EvolutionRuleError.code: 400,
    InvalidCursorError.code: 400,
    NotFoundError.code: 404,
    IdempotencyKeyRequiredError.code: 400,
    IdempotencyConflictError.code: 409,
    StorageUnavailableError.code: 503,
}


def error_body(
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "details": details,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError):
        status = STATUS_BY_CODE.get(exc.code, 400)
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse(
            error_body(exc.code, exc.message, exc.field, exc.details),
            status_code=status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        location = [str(part) for part in first["loc"] if part not in ("body",)]
        field = location[-1] if location else None
        message = f"El campo {field or 'enviado'} no es válido: {first['msg']}."
        return JSONResponse(
            error_body("invalid_field", message, field), status_code=400
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(
            error_body(code, str(exc.detail)), status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Error no controlado", exc_info=exc)
        return JSONResponse(
            error_body("internal_error", "Ocurrió un error inesperado."),
            status_code=500,
        )


# ======================================================================
# Aplicación
# ======================================================================


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    mongo_database=None,
) -> FastAPI:
    """Crea la aplicación. Los parámetros opcionales permiten inyectar pruebas."""
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        mongo_client = None
        factory, database = session_factory, mongo_database
        if factory is None:
            engine = create_engine(settings.database_url)
            await init_db(engine)
            factory = create_session_factory(engine)
        if database is None:
            mongo_client = AsyncIOMotorClient(settings.mongo_url)
            database = mongo_client[settings.mongo_db_name]

        container = build_container(settings, factory, database)
        await container.card_images.ensure_indexes()
        await container.location_images.ensure_indexes()
        app.state.container = container

        stop = asyncio.Event()
        worker = None
        if settings.run_image_worker:
            worker = asyncio.create_task(
                run_image_worker(
                    container.image_processing,
                    settings.image_worker_poll_seconds,
                    stop,
                )
            )
        try:
            yield
        finally:
            stop.set()
            if worker is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
            if mongo_client is not None:
                mongo_client.close()
            if engine is not None:
                await engine.dispose()

    app = FastAPI(title="PokéArena Backoffice API", version="0.2.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(cartas.router)
    app.include_router(ubicaciones.router)

    @app.get("/health", tags=["Salud"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
