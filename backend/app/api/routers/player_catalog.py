"""API del jugador: explorar el catálogo de cartas y su colección."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.caching import compute_etag, etag_matches
from app.api.gateway.authentication import require_player
from app.api.gateway.errors import (
    AUTH_ERROR_RESPONSES,
    NOT_FOUND_RESPONSE,
    ErrorResponse,
)
from app.api.schemas.player_catalog import (
    CardTypesResponse,
    PlayerCardOut,
    PlayerCatalogResponse,
)
from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.search.models import CatalogBrowseRequest
from app.business.collection.catalog_browser import CatalogBrowser, CatalogEntry
from app.business.identity_access.roles import Actor

router = APIRouter(prefix="/v1", tags=["Jugador"])

CACHE_CONTROL = "private, no-cache"


def get_catalog_browser(request: Request) -> CatalogBrowser:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.catalog_browser


def get_reference_service(request: Request) -> ReferenceService:
    return request.app.state.reference_service


def get_card_search_service(request: Request) -> CardSearchService:
    return request.app.state.card_search_service


def _to_card(entry: CatalogEntry) -> PlayerCardOut:
    card = entry.card
    return PlayerCardOut(
        code=card.code,
        name=card.name,
        cost=card.cost,
        power=card.power,
        card_type=CardTypeOut(**asdict(card.card_type)),
        rarity=RarityOut(**asdict(card.rarity)),
        ability=AbilityOut(**asdict(card.ability)),
        image_url=f"/v1/cartas/{card.code}/imagen",
        owned=entry.owned,
        copies=entry.copies,
    )


@router.get(
    "/referencias",
    response_model=CardTypesResponse,
    summary="Cargar los tipos de carta",
    description=(
        "Tipos que el jugador puede usar como filtro del catálogo. Incluye ETag: "
        "con If-None-Match la API responde 304 si no hay cambios."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        304: {"description": "Las referencias no han cambiado."},
    },
)
def get_player_references(
    _actor: Actor = Depends(require_player),
    service: ReferenceService = Depends(get_reference_service),
    if_none_match: str | None = Header(default=None),
) -> Response:
    payload = CardTypesResponse(
        card_types=[CardTypeOut(**asdict(t)) for t in service.get_card_types()]
    ).model_dump()
    etag = compute_etag(payload)
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


@router.get(
    "/cartas",
    response_model=PlayerCatalogResponse,
    summary="Explorar el catálogo y mi colección",
    description=(
        "Cartas Disponibles del catálogo, por páginas. Cada una indica si el jugador "
        "la posee y cuántas copias tiene. Los filtros son opcionales y los activos se "
        "cumplen a la vez: tipo, costo exacto (cost) o rango (cost_min y cost_max), y "
        "owned_only para ver solo las cartas propias. Sin resultados devuelve una "
        "lista vacía. Usa el next_cursor de cada respuesta como last_id de la "
        "siguiente hasta que sea nulo. Una carta recién creada aparece cuando su "
        "imagen termina de procesarse, unos segundos después."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Filtro o paginación inválidos; indica los valores permitidos.",
        },
        **AUTH_ERROR_RESPONSES,
    },
)
def browse_catalog(
    request: Request,
    card_type: str | None = Query(default=None, description="Código del tipo, ej. FUE"),
    cost: int | None = Query(default=None, description="Costo exacto"),
    cost_min: int | None = Query(default=None, description="Costo mínimo"),
    cost_max: int | None = Query(default=None, description="Costo máximo"),
    owned_only: bool = Query(default=False, description="Solo las cartas que poseo"),
    limit: int | None = Query(default=None, description="Cartas por página (1 a 100)"),
    last_id: int | None = Query(
        default=None, description="Cursor de la página anterior"
    ),
    actor: Actor = Depends(require_player),
    browser: CatalogBrowser = Depends(get_catalog_browser),
) -> PlayerCatalogResponse:
    """Devuelve una página del catálogo con las copias del jugador."""
    page = browser.browse(
        actor.user_id,
        CatalogBrowseRequest(
            card_type=card_type,
            cost=cost,
            cost_min=cost_min,
            cost_max=cost_max,
            limit=limit,
            last_id=last_id,
        ),
        only_owned=owned_only,
    )
    return PlayerCatalogResponse(
        items=[_to_card(entry) for entry in page.items], next_cursor=page.next_cursor
    )


@router.get(
    "/cartas/{code}/imagen",
    summary="Ver la imagen de una carta",
    description="Devuelve la versión grande de la imagen de una carta Disponible.",
    response_class=Response,
    responses={
        200: {"content": {"image/*": {}}, "description": "La imagen."},
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
    },
)
def get_card_image(
    code: str,
    _actor: Actor = Depends(require_player),
    search: CardSearchService = Depends(get_card_search_service),
) -> Response:
    # Pasos 57–68: la imagen la da Búsqueda directamente, solo de cartas Disponibles.
    image = search.get_card_image(code, only_available=True)
    return Response(
        content=image.data,
        media_type=image.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
