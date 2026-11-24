"""API de búsqueda del jugador autenticado."""

from fastapi import APIRouter, Depends, Request, Response

from app.api.gateway.authentication import require_player
from app.api.gateway.errors import AUTH_ERROR_RESPONSES, ErrorResponse
from app.api.gateway.idempotency import IDEMPOTENCY_HEADER, MAX_KEY_LENGTH
from app.api.gateway.search_access import SearchAccess, require_search_access
from app.api.schemas.player_searches import SearchRequest, SearchResponse
from app.business.identity_access.roles import Actor
from app.business.matchmaking.elo_queue import EloQueue
from app.business.shared.errors import ServiceUnavailableError

router = APIRouter(prefix="/v1/busquedas", tags=["Jugador"])
SEARCH_ERRORS = {
    **AUTH_ERROR_RESPONSES,
    404: {
        "model": ErrorResponse,
        "description": "Deck o búsqueda no disponible para el jugador",
    },
    503: {"model": ErrorResponse, "description": "Dependencia no disponible"},
}


def get_queue(request: Request) -> EloQueue:
    queue = request.app.state.elo_queue
    if queue is None:
        raise ServiceUnavailableError("La búsqueda de partida no está disponible.")
    return queue


@router.post(
    "",
    response_model=SearchResponse,
    status_code=202,
    summary="Buscar partida clasificatoria",
    description=(
        "Ingresa a la fila con un mazo propio de 12 cartas distintas y un saldo "
        "mínimo de 8 cubos. Repite la misma clave para recuperar la búsqueda."
    ),
    openapi_extra={
        "parameters": [
            {
                "name": IDEMPOTENCY_HEADER,
                "in": "header",
                "required": True,
                "schema": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_KEY_LENGTH,
                },
            }
        ]
    },
    responses={
        **SEARCH_ERRORS,
        200: {"model": SearchResponse, "description": "Búsqueda existente"},
        400: {
            "model": ErrorResponse,
            "description": "Deck, saldo o clave de operación inválidos",
        },
        409: {
            "model": ErrorResponse,
            "description": "Partida activa, búsqueda incompatible o clave reutilizada",
        },
        429: {"model": ErrorResponse, "description": "Límite de solicitudes alcanzado"},
        "4XX": {
            "model": ErrorResponse,
            "description": "Error de solicitud con el formato común",
        },
    },
)
def create_search(
    response: Response,
    body: SearchRequest | None = None,
    access: SearchAccess = Depends(require_search_access),
    queue: EloQueue = Depends(get_queue),
) -> SearchResponse:
    # En un reintento, consulta el estado actual de la búsqueda del jugador.
    deck_id = body.deck_id.strip().lower() if body and body.deck_id else None
    previous = access.previous_search(deck_id)
    if previous is not None:
        search, created = queue.get(access.actor.user_id, previous), False
    else:
        search, created = queue.enter(
            access.actor.user_id, deck_id, key_hash=access.key_hash
        )
    result = SearchResponse.model_validate(search)
    access.respond(response, result, created=created)
    return result


@router.get("/actual", response_model=SearchResponse | None, responses=SEARCH_ERRORS)
def current_search(
    response: Response,
    actor: Actor = Depends(require_player),
    queue: EloQueue = Depends(get_queue),
):
    response.headers["Cache-Control"] = "no-store"
    return queue.current(actor.user_id)


@router.get("/{search_id}", response_model=SearchResponse, responses=SEARCH_ERRORS)
def get_search(
    search_id: str,
    response: Response,
    actor: Actor = Depends(require_player),
    queue: EloQueue = Depends(get_queue),
):
    response.headers["Cache-Control"] = "no-store"
    return queue.get(actor.user_id, search_id)


@router.post(
    "/{search_id}/cancelar", response_model=SearchResponse, responses=SEARCH_ERRORS
)
def cancel_search(
    search_id: str,
    response: Response,
    actor: Actor = Depends(require_player),
    queue: EloQueue = Depends(get_queue),
):
    response.headers["Cache-Control"] = "no-store"
    return queue.cancel(actor.user_id, search_id)
