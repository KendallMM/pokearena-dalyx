"""Ubicaciones: repositorio, caso de uso (crear) y rutas HTTP."""

import asyncio
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Response,
    UploadFile,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import (
    CreationFlow,
    CreationResult,
    ImageJobRepository,
    Principal,
    compute_request_hash,
    ensure_decodable,
    get_container,
    inspect_image,
    parse_idempotency_key,
    require_admin,
)
from app.engine.ability_engine import (
    CONTENT_TYPE_BY_FORMAT,
    LOCATION_IMAGE_SPEC,
    STATUS_PENDING_IMAGE,
    ImageRequirementError,
    LocationDraft,
    NotFoundError,
    validate_image_info,
    validate_image_size,
    validate_location_draft,
)
from app.models.carta_model import (
    ENTITY_LOCATION_VERSION,
)
from app.models.ubicacion_model import (
    GameLocation,
    GameLocationVersion,
)
from app.routers.cartas import (
    read_upload,
)
from app.schemas.carta_schema import ErrorResponse
from app.schemas.ubicacion_schema import (
    LocationCreationResponse,
    LocationStatusResponse,
)

# ======================================================================
# Repositorio de ubicaciones
# ======================================================================


class GameLocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_location(self) -> GameLocation:
        location = GameLocation()
        self._session.add(location)
        await self._session.flush()
        return location

    async def add_version(self, version: GameLocationVersion) -> GameLocationVersion:
        self._session.add(version)
        await self._session.flush()
        return version

    async def latest_version(self, location_id: int) -> GameLocationVersion | None:
        return await self._session.scalar(
            select(GameLocationVersion)
            .where(GameLocationVersion.game_location_id == location_id)
            .order_by(GameLocationVersion.version.desc())
            .limit(1)
        )

    async def get_version(self, version_id: int) -> GameLocationVersion | None:
        return await self._session.get(GameLocationVersion, version_id)

    async def set_version_status(self, version_id: int, status: str) -> None:
        await self._session.execute(
            update(GameLocationVersion)
            .where(GameLocationVersion.id == version_id)
            .values(status=status)
        )


# ======================================================================
# Caso de uso: crear ubicación
# ======================================================================

ENDPOINT = "POST /admin/ubicaciones"
FIRST_VERSION = 1


class GameLocationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        flow: CreationFlow,
    ) -> None:
        self._session_factory = session_factory
        self._flow = flow

    async def create_location(
        self,
        *,
        user_id: str,
        idempotency_key: str | None,
        name: str | None,
        description: str | None,
        effect_type: str | None,
        effect_card_type: str | None,
        effect_amount: int | None,
        effect_restricted_turns: list[int] | None,
        card_limit: int | None,
        extra_energy_mode: str | None,
        extra_energy_amount: int | None,
        image: bytes | None,
    ) -> CreationResult:
        key = parse_idempotency_key(idempotency_key)
        request_hash = compute_request_hash(
            {
                "name": name,
                "description": description,
                "effect_type": effect_type,
                "effect_card_type": effect_card_type,
                "effect_amount": effect_amount,
                "effect_restricted_turns": effect_restricted_turns,
                "card_limit": card_limit,
                "extra_energy_mode": extra_energy_mode,
                "extra_energy_amount": extra_energy_amount,
            },
            image,
        )
        replay = await self._flow.find_replay(user_id, ENDPOINT, key, request_hash)
        if replay is not None:
            return replay

        draft = validate_location_draft(
            name=name,
            description=description,
            effect_type=effect_type,
            effect_card_type=effect_card_type,
            effect_amount=effect_amount,
            effect_restricted_turns=effect_restricted_turns,
            card_limit=card_limit,
            extra_energy_mode=extra_energy_mode,
            extra_energy_amount=extra_energy_amount,
        )
        image_format = await self._validate_image(image)
        assert image is not None
        image_ref = uuid.uuid4().hex

        async def build(session: AsyncSession):
            return await self._create_in_transaction(session, draft, user_id, image_ref)

        return await self._flow.execute(
            user_id=user_id,
            endpoint=ENDPOINT,
            key=key,
            request_hash=request_hash,
            image_ref=image_ref,
            content_type=CONTENT_TYPE_BY_FORMAT[image_format],
            image_bytes=image,
            build=build,
        )

    @staticmethod
    async def _validate_image(image: bytes | None) -> str:
        if image is None:
            raise ImageRequirementError(
                "La imagen es obligatoria.",
                field="image",
                details={"requirement": "required"},
            )
        validate_image_size(len(image))
        info = await asyncio.to_thread(inspect_image, image)
        validate_image_info(info, LOCATION_IMAGE_SPEC)
        await asyncio.to_thread(ensure_decodable, image)
        return info.image_format

    @staticmethod
    async def _create_in_transaction(
        session: AsyncSession, draft: LocationDraft, user_id: str, image_ref: str
    ):
        locations = GameLocationRepository(session)
        location = await locations.add_location()
        effect = draft.effect
        version = await locations.add_version(
            GameLocationVersion(
                game_location_id=location.id,
                version=FIRST_VERSION,
                name=draft.name,
                description=draft.description,
                effect_type=effect.effect_type if effect else None,
                effect_parameters=effect.parameters if effect else {},
                card_limit=draft.card_limit,
                extra_energy_mode=draft.extra_energy_mode,
                extra_energy_amount=draft.extra_energy_amount,
                status=STATUS_PENDING_IMAGE,
                image_ref=image_ref,
                created_by=user_id,
            )
        )
        job = await ImageJobRepository(session).add(
            ENTITY_LOCATION_VERSION, version.id, image_ref
        )
        body = {
            "id": location.id,
            "version": version.version,
            "status": version.status,
            "status_url": f"/admin/ubicaciones/{location.id}/estado",
        }
        return body, job.id

    async def get_status(self, location_id: int) -> dict:
        async with self._session_factory() as session:
            version = await GameLocationRepository(session).latest_version(location_id)
            if version is None:
                raise NotFoundError("La ubicación no existe.", field="id")
            job = await ImageJobRepository(session).latest_for(
                ENTITY_LOCATION_VERSION, version.id
            )
        return {
            "id": location_id,
            "version": version.version,
            "status": version.status,
            "image_processing": job.status if job else None,
        }


# ======================================================================
# Rutas HTTP de ubicaciones
# ======================================================================

router = APIRouter(prefix="/admin/ubicaciones", tags=["Ubicaciones"])

_ERRORS = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
}


@router.post(
    "",
    status_code=202,
    response_model=LocationCreationResponse,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
async def create_location(
    response: Response,
    background: BackgroundTasks,
    principal: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    effect_type: str | None = Form(default=None),
    effect_card_type: str | None = Form(default=None),
    effect_amount: int | None = Form(default=None),
    effect_restricted_turns: list[int] | None = Form(default=None),
    card_limit: int | None = Form(default=None),
    extra_energy_mode: str | None = Form(default=None),
    extra_energy_amount: int | None = Form(default=None),
    image: UploadFile | None = File(default=None),
):
    result = await container.location_service.create_location(
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        name=name,
        description=description,
        effect_type=effect_type,
        effect_card_type=effect_card_type,
        effect_amount=effect_amount,
        effect_restricted_turns=effect_restricted_turns,
        card_limit=card_limit,
        extra_energy_mode=extra_energy_mode,
        extra_energy_amount=extra_energy_amount,
        image=await read_upload(image),
    )
    response.status_code = result.status_code
    if result.job_id is not None:
        background.add_task(container.image_processing.process_job, result.job_id)
    return result.body


@router.get(
    "/{location_id}/estado", response_model=LocationStatusResponse, responses=_ERRORS
)
async def location_status(
    location_id: int,
    _: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
):
    return await container.location_service.get_status(location_id)
