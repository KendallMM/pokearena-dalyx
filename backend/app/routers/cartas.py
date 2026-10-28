"""Cartas: repositorios, casos de uso (crear y buscar) y rutas HTTP.

Dentro del archivo las capas están separadas por secciones:
repositorios -> servicios -> router.
"""

import asyncio
import uuid
from typing import Any, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import (
    CreationFlow,
    CreationResult,
    ImageJobRepository,
    ImageStore,
    Principal,
    compute_request_hash,
    decode_cursor,
    encode_cursor,
    ensure_decodable,
    get_container,
    inspect_image,
    parse_idempotency_key,
    require_admin,
)
from app.engine.ability_engine import (
    CARD_IMAGE_SPEC,
    CONTENT_TYPE_BY_FORMAT,
    MAX_IMAGE_BYTES,
    STATUS_PENDING_IMAGE,
    STATUS_READY,
    CardDraft,
    CardSearchCriteria,
    ImageRequirementError,
    InvalidAbilityError,
    InvalidCursorError,
    InvalidFieldError,
    NotFoundError,
    ability_engine,
    ensure_evolution_is_valid,
    escape_like,
    format_card_code,
    validate_card_draft,
    validate_image_info,
    validate_image_size,
    validate_page_limit,
    validate_search_criteria,
)
from app.models.carta_model import (
    ENTITY_CARD,
    Ability,
    Card,
    CardCodeCounter,
)
from app.schemas.carta_schema import (
    CardCreationResponse,
    CardSearchResponse,
    CardStatusResponse,
    ErrorResponse,
)

# ======================================================================
# Repositorio de habilidades
# ======================================================================


class AbilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> Ability | None:
        return await self._session.scalar(select(Ability).where(Ability.code == code))

    async def evolution_edges(self) -> dict[str, str]:
        """Mapa carta -> carta destino de las evoluciones ya registradas."""
        rows = await self._session.execute(
            select(Card.code, Card.evolution_target_code).where(
                Card.evolution_target_code.is_not(None)
            )
        )
        return {code: target for code, target in rows.all()}


# ======================================================================
# Repositorio de cartas
# ======================================================================


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_sequence(self, card_type: str) -> int:
        """Entrega el siguiente consecutivo del tipo, sin repetir ni saltar.

        El UPDATE toma el bloqueo del renglón del contador hasta que termina la
        transacción; otra solicitud del mismo tipo espera, así no hay códigos
        duplicados aunque lleguen en paralelo. Si la transacción se revierte,
        el contador también, y el número no se pierde.
        """
        await self._session.execute(
            update(CardCodeCounter)
            .where(CardCodeCounter.card_type == card_type)
            .values(last_number=CardCodeCounter.last_number + 1)
        )
        return await self._session.scalar(
            select(CardCodeCounter.last_number).where(
                CardCodeCounter.card_type == card_type
            )
        )

    async def add(self, card: Card) -> Card:
        self._session.add(card)
        await self._session.flush()
        return card

    async def get_with_ability(self, code: str) -> tuple[Card, Ability] | None:
        row = (
            await self._session.execute(
                select(Card, Ability)
                .join(Ability, Ability.id == Card.ability_id)
                .where(Card.code == code)
            )
        ).first()
        return None if row is None else (row[0], row[1])

    async def set_status(self, card_id: int, status: str) -> None:
        await self._session.execute(
            update(Card).where(Card.id == card_id).values(status=status)
        )

    async def get(self, card_id: int) -> Card | None:
        return await self._session.get(Card, card_id)

    async def max_id(self) -> int | None:
        return await self._session.scalar(select(func.max(Card.id)))

    async def search(
        self,
        criteria: CardSearchCriteria,
        *,
        max_id: int,
        last_id: int,
        limit: int,
    ) -> list[tuple[Card, Ability]]:
        """Página de cartas ordenadas por ``id``; pide una de más para ``has_more``."""
        statement = (
            select(Card, Ability)
            .join(Ability, Ability.id == Card.ability_id)
            .where(Card.id <= max_id, Card.id > last_id)
        )
        if criteria.code:
            statement = statement.where(Card.code == criteria.code)
        if criteria.name_search:
            pattern = f"%{escape_like(criteria.name_search)}%"
            statement = statement.where(Card.name_search.like(pattern, escape="\\"))
        if criteria.cost_min is not None:
            statement = statement.where(Card.cost >= criteria.cost_min)
        if criteria.cost_max is not None:
            statement = statement.where(Card.cost <= criteria.cost_max)
        if criteria.power_min is not None:
            statement = statement.where(Card.power >= criteria.power_min)
        if criteria.power_max is not None:
            statement = statement.where(Card.power <= criteria.power_max)
        if criteria.card_type:
            statement = statement.where(Card.card_type == criteria.card_type)
        if criteria.rarity:
            statement = statement.where(Card.rarity == criteria.rarity)
        if criteria.ability_code:
            statement = statement.where(Ability.code == criteria.ability_code)
        if criteria.ability_trigger:
            statement = statement.where(
                Ability.trigger_type == criteria.ability_trigger
            )
        if criteria.ability_effect:
            statement = statement.where(Ability.effect_type == criteria.ability_effect)
        rows = await self._session.execute(statement.order_by(Card.id).limit(limit + 1))
        return [(row[0], row[1]) for row in rows.all()]


# ======================================================================
# Armado de respuestas
# ======================================================================


def card_image_urls(card: Card) -> dict[str, str] | None:
    if card.status != STATUS_READY:
        return None
    base = f"/admin/cartas/{card.code}/imagen"
    return {"large": f"{base}?version=large", "small": f"{base}?version=small"}


def card_summary(card: Card, ability: Ability) -> dict[str, Any]:
    return {
        "code": card.code,
        "name": card.name,
        "cost": card.cost,
        "power": card.power,
        "type": card.card_type,
        "rarity": card.rarity,
        "status": card.status,
        "ability": {
            "code": ability.code,
            "name": ability.name,
            "trigger_type": ability.trigger_type,
            "condition_type": ability.condition_type,
            "effect_type": ability.effect_type,
            "target_type": ability.target_type,
            "affected_type": ability.affected_type,
            "parameters": ability.parameters or {},
        },
        "image": card_image_urls(card),
    }


# ======================================================================
# Caso de uso: crear carta
# ======================================================================

ENDPOINT = "POST /admin/cartas"


class CardService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        image_store: ImageStore,
        flow: CreationFlow,
    ) -> None:
        self._session_factory = session_factory
        self._store = image_store
        self._flow = flow

    async def create_card(
        self,
        *,
        user_id: str,
        idempotency_key: str | None,
        name: str | None,
        cost: int | None,
        power: int | None,
        card_type: str | None,
        rarity: str | None,
        ability: str | None,
        image: bytes | None,
    ) -> CreationResult:
        key = parse_idempotency_key(idempotency_key)
        request_hash = compute_request_hash(
            {
                "name": name,
                "cost": cost,
                "power": power,
                "type": card_type,
                "rarity": rarity,
                "ability": ability,
            },
            image,
        )
        replay = await self._flow.find_replay(user_id, ENDPOINT, key, request_hash)
        if replay is not None:
            return replay

        draft = validate_card_draft(
            name=name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            ability_code=ability,
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
        """Orden: existe -> peso -> formato real -> resolución -> proporción."""
        if image is None:
            raise ImageRequirementError(
                "La imagen es obligatoria.",
                field="image",
                details={"requirement": "required"},
            )
        validate_image_size(len(image))
        info = await asyncio.to_thread(inspect_image, image)
        validate_image_info(info, CARD_IMAGE_SPEC)
        await asyncio.to_thread(ensure_decodable, image)
        return info.image_format

    @staticmethod
    async def _create_in_transaction(
        session: AsyncSession, draft: CardDraft, user_id: str, image_ref: str
    ):
        abilities = AbilityRepository(session)
        cards = CardRepository(session)
        ability = await abilities.get_by_code(draft.ability_code)
        if ability is None:
            raise InvalidAbilityError(
                f"La habilidad {draft.ability_code} no existe.", field="ability"
            )
        code = format_card_code(
            draft.card_type, await cards.next_sequence(draft.card_type)
        )
        target = ability_engine.evolution_target(
            ability.effect_type, ability.parameters
        )
        edges = await abilities.evolution_edges() if target else {}
        ensure_evolution_is_valid(code, target, edges)

        card = await cards.add(
            Card(
                code=code,
                name=draft.name,
                name_search=draft.name_search,
                cost=draft.cost,
                power=draft.power,
                card_type=draft.card_type,
                rarity=draft.rarity,
                ability_id=ability.id,
                evolution_target_code=target,
                status=STATUS_PENDING_IMAGE,
                image_ref=image_ref,
                created_by=user_id,
            )
        )
        job = await ImageJobRepository(session).add(ENTITY_CARD, card.id, image_ref)
        body = {
            "code": code,
            "status": card.status,
            "status_url": f"/admin/cartas/{code}/estado",
        }
        return body, job.id

    async def get_status(self, code: str) -> dict:
        async with self._session_factory() as session:
            found = await CardRepository(session).get_with_ability(code.upper())
            if found is None:
                raise NotFoundError("La carta no existe.", field="code")
            card, ability = found
            job = await ImageJobRepository(session).latest_for(ENTITY_CARD, card.id)
        return {
            "code": card.code,
            "status": card.status,
            "image_processing": job.status if job else None,
            "ability": {"code": ability.code, "affected_type": ability.affected_type},
        }

    async def get_image(self, code: str, version: str) -> tuple[bytes, str]:
        async with self._session_factory() as session:
            found = await CardRepository(session).get_with_ability(code.upper())
        if found is None:
            raise NotFoundError("La carta no existe.", field="code")
        document = await self._store.get(found[0].image_ref)
        if version == "small":
            data = document and document.get("thumbnail")
            media = document and document.get("thumbnail_content_type")
        else:
            data = document and document.get("original")
            media = document and document.get("content_type")
        if not data:
            raise NotFoundError("La imagen todavía no está disponible.")
        return bytes(data), media or "application/octet-stream"


# ======================================================================
# Caso de uso: buscar cartas
# ======================================================================


class CardSearchService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], cursor_secret: str
    ) -> None:
        self._session_factory = session_factory
        self._secret = cursor_secret

    async def search(
        self,
        *,
        cursor: str | None,
        limit: int | None,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        explicit_limit = None if limit is None else validate_page_limit(limit)
        cursor = (cursor or "").strip() or None
        active = {
            k: v
            for k, v in filters.items()
            if v is not None and not (isinstance(v, str) and not v.strip())
        }

        async with self._session_factory() as session:
            repository = CardRepository(session)
            if cursor is not None:
                if active:
                    raise InvalidFieldError(
                        "No se pueden combinar cursor y filtros: el cursor ya "
                        "recuerda los filtros de la primera página.",
                        field="cursor",
                    )
                criteria, max_id, last_id, remembered = self._read_cursor(cursor)
                # Sin limit explícito, la página siguiente conserva el tamaño anterior.
                page_size = explicit_limit or remembered
            else:
                page_size = explicit_limit or validate_page_limit(None)
                criteria = validate_search_criteria(**filters)
                max_id = await repository.max_id()
                last_id = 0
                if max_id is None:
                    return {"items": [], "next_cursor": None, "has_more": False}
            rows = await repository.search(
                criteria, max_id=max_id, last_id=last_id, limit=page_size
            )

        has_more = len(rows) > page_size
        page = rows[:page_size]
        next_cursor = None
        if has_more:
            next_cursor = encode_cursor(
                {
                    "c": criteria.to_dict(),
                    "m": max_id,
                    "l": page[-1][0].id,
                    "s": page_size,
                },
                self._secret,
            )
        return {
            "items": [card_summary(card, ability) for card, ability in page],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def _read_cursor(self, cursor: str) -> tuple[CardSearchCriteria, int, int, int]:
        payload = decode_cursor(cursor, self._secret)
        try:
            criteria = CardSearchCriteria(**payload["c"])
            max_id, last_id, size = payload["m"], payload["l"], payload["s"]
        except (KeyError, TypeError):
            raise InvalidCursorError(
                "El cursor no es válido.", field="cursor"
            ) from None
        numbers = (max_id, last_id, size)
        if not all(type(n) is int for n in numbers):
            raise InvalidCursorError("El cursor no es válido.", field="cursor")
        try:
            size = validate_page_limit(size)
        except InvalidFieldError:
            raise InvalidCursorError(
                "El cursor no es válido.", field="cursor"
            ) from None
        return criteria, max_id, last_id, size


# ======================================================================
# Rutas HTTP de cartas
# ======================================================================

router = APIRouter(prefix="/admin/cartas", tags=["Cartas"])

_ERRORS = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
}


async def read_upload(upload: UploadFile | None) -> bytes | None:
    """Lee a lo más 5 MB + 1 byte: basta para saber si se pasó del límite."""
    if upload is None:
        return None
    return await upload.read(MAX_IMAGE_BYTES + 1)


@router.post(
    "",
    status_code=202,
    response_model=CardCreationResponse,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
async def create_card(
    response: Response,
    background: BackgroundTasks,
    principal: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    name: str | None = Form(default=None),
    cost: int | None = Form(default=None),
    power: int | None = Form(default=None),
    card_type: str | None = Form(default=None, alias="type"),
    rarity: str | None = Form(default=None),
    ability: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
):
    result = await container.card_service.create_card(
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        name=name,
        cost=cost,
        power=power,
        card_type=card_type,
        rarity=rarity,
        ability=ability,
        image=await read_upload(image),
    )
    response.status_code = result.status_code
    if result.job_id is not None:
        background.add_task(container.image_processing.process_job, result.job_id)
    return result.body


@router.get("", response_model=CardSearchResponse, responses=_ERRORS)
async def search_cards(
    _: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
    code: str | None = Query(default=None),
    name: str | None = Query(default=None),
    cost: int | None = Query(default=None),
    cost_min: int | None = Query(default=None),
    cost_max: int | None = Query(default=None),
    power: int | None = Query(default=None),
    power_min: int | None = Query(default=None),
    power_max: int | None = Query(default=None),
    card_type: str | None = Query(default=None, alias="type"),
    rarity: str | None = Query(default=None),
    ability_code: str | None = Query(default=None),
    ability_trigger: str | None = Query(default=None),
    ability_effect: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
):
    return await container.search_service.search(
        cursor=cursor,
        limit=limit,
        filters={
            "code": code,
            "name": name,
            "cost": cost,
            "cost_min": cost_min,
            "cost_max": cost_max,
            "power": power,
            "power_min": power_min,
            "power_max": power_max,
            "card_type": card_type,
            "rarity": rarity,
            "ability_code": ability_code,
            "ability_trigger": ability_trigger,
            "ability_effect": ability_effect,
        },
    )


@router.get("/{code}/estado", response_model=CardStatusResponse, responses=_ERRORS)
async def card_status(
    code: str,
    _: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
):
    return await container.card_service.get_status(code)


@router.get("/{code}/imagen", responses={**_ERRORS, 404: {"model": ErrorResponse}})
async def card_image(
    code: str,
    version: Literal["large", "small"] = Query(default="large"),
    _: Principal = Depends(require_admin),
    container: Any = Depends(get_container),
):
    data, media_type = await container.card_service.get_image(code, version)
    return Response(content=data, media_type=media_type)
