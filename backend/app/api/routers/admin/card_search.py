"""API de Administración: buscar cartas y ver su imagen."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.gateway.authentication import require_content_admin
from app.api.gateway.errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE
from app.api.schemas.card_search import CardResultOut, CardSearchResponse
from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.search.models import CardSearchRequest, CardSummary
from app.business.identity_access.roles import Actor

router = APIRouter(prefix="/admin", tags=["Administración"])


def get_card_search_service(request: Request) -> CardSearchService:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.card_search_service


def _to_result(card: CardSummary) -> CardResultOut:
    return CardResultOut(
        code=card.code,
        name=card.name,
        cost=card.cost,
        power=card.power,
        card_type=CardTypeOut(**asdict(card.card_type)),
        rarity=RarityOut(**asdict(card.rarity)),
        ability=AbilityOut(**asdict(card.ability)),
        image_url=f"/admin/cartas/{card.code}/imagen",
        image_status=card.status.value,
        thumbnail_attempts=card.thumbnail_attempts,
    )


@router.get(
    "/cartas",
    response_model=CardSearchResponse,
    summary="Buscar cartas",
    description=(
        "Busca en el catálogo completo (incluye las cartas con imagen pendiente). Todos "
        "los criterios son opcionales y los activos se cumplen a la vez. El nombre "
        "acepta coincidencia parcial sin distinguir mayúsculas ni tildes. Costo y poder "
        "aceptan un valor exacto (cost) o un rango (cost_min y cost_max). Los resultados "
        "se ordenan por antigüedad y se piden por páginas: usa el next_cursor de cada "
        "respuesta como last_id de la siguiente hasta que sea nulo."
    ),
    responses={**AUTH_ERROR_RESPONSES, 400: {"description": "Criterio inválido."}},
)
def search_cards(
    code: str | None = Query(
        default=None, description="Código exacto, ej. PKA-FUE-001"
    ),
    name: str | None = Query(default=None, description="Parte del nombre"),
    cost: int | None = Query(default=None, description="Costo exacto"),
    cost_min: int | None = Query(default=None, description="Costo mínimo"),
    cost_max: int | None = Query(default=None, description="Costo máximo"),
    power: int | None = Query(default=None, description="Poder exacto"),
    power_min: int | None = Query(default=None, description="Poder mínimo"),
    power_max: int | None = Query(default=None, description="Poder máximo"),
    card_type: str | None = Query(default=None, description="Código del tipo, ej. FUE"),
    rarity: str | None = Query(default=None, description="Código de la rareza"),
    ability: str | None = Query(default=None, description="Código, ej. HAB-000"),
    limit: int | None = Query(default=None, description="Cartas por página (1 a 100)"),
    last_id: int | None = Query(
        default=None, description="Cursor de la página anterior"
    ),
    _actor: Actor = Depends(require_content_admin),
    service: CardSearchService = Depends(get_card_search_service),
) -> CardSearchResponse:
    """Devuelve una página de cartas y el cursor de la siguiente."""
    page = service.search_cards(
        CardSearchRequest(
            code=code,
            name=name,
            cost=cost,
            cost_min=cost_min,
            cost_max=cost_max,
            power=power,
            power_min=power_min,
            power_max=power_max,
            card_type=card_type,
            rarity=rarity,
            ability=ability,
            limit=limit,
            last_id=last_id,
        )
    )
    return CardSearchResponse(
        items=[_to_result(card) for card in page.items], next_cursor=page.next_cursor
    )


@router.get(
    "/cartas/{code}/imagen",
    summary="Ver la imagen de una carta",
    description="Devuelve la versión grande de la imagen de la carta.",
    response_class=Response,
    responses={
        200: {"content": {"image/*": {}}, "description": "La imagen."},
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
    },
)
def get_card_image(
    code: str,
    _actor: Actor = Depends(require_content_admin),
    service: CardSearchService = Depends(get_card_search_service),
) -> Response:
    """Entrega los bytes de la imagen con su tipo de contenido."""
    image = service.get_card_image(code)
    return Response(
        content=image.data,
        media_type=image.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
