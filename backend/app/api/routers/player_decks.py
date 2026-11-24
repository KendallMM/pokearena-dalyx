"""API del jugador: crear y consultar sus decks."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.gateway.authentication import require_player
from app.api.gateway.errors import (
    AUTH_ERROR_RESPONSES,
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    ErrorResponse,
)
from app.api.gateway.idempotency import (
    IdempotencyContext,
    player_idempotency_context,
)
from app.api.schemas.player_decks import (
    CreateDeckRequest,
    DeckCardOut,
    DeckCreatedResponse,
    DeckListResponse,
    DeckOut,
)
from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut
from app.business.collection.decks import Deck, DeckService
from app.business.identity_access.roles import Actor

router = APIRouter(prefix="/v1/mazos", tags=["Jugador"])


def get_deck_service(request: Request) -> DeckService:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.deck_service


def _to_deck(deck: Deck) -> DeckOut:
    return DeckOut(
        id=deck.id,
        name=deck.name,
        cards=[
            DeckCardOut(
                code=card.code,
                name=card.name,
                cost=card.cost,
                power=card.power,
                card_type=CardTypeOut(**asdict(card.card_type)),
                rarity=RarityOut(**asdict(card.rarity)),
                ability=AbilityOut(**asdict(card.ability)),
                image_url=f"/v1/cartas/{card.code}/imagen",
            )
            for card in deck.cards
        ],
    )


@router.post(
    "",
    status_code=201,
    response_model=DeckCreatedResponse,
    summary="Crear un deck",
    description=(
        "Crea un deck con un nombre y 12 cartas distintas de la colección del jugador. "
        "Requiere el encabezado Idempotency-Key: repetir la misma operación devuelve "
        "la respuesta guardada sin crear otro deck."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Nombre o cartas inválidos."},
        **AUTH_ERROR_RESPONSES,
        **CONFLICT_RESPONSE,
    },
)
def create_deck(
    body: CreateDeckRequest,
    actor: Actor = Depends(require_player),
    ctx: IdempotencyContext = Depends(player_idempotency_context),
    service: DeckService = Depends(get_deck_service),
) -> JSONResponse:
    created = service.create(actor.user_id, body.name, body.cards)
    return ctx.respond(201, DeckCreatedResponse(**asdict(created)))


@router.get(
    "",
    response_model=DeckListResponse,
    summary="Consultar mis decks",
    description="Decks del jugador autenticado; lista vacía si no tiene.",
    responses=AUTH_ERROR_RESPONSES,
)
def list_decks(
    actor: Actor = Depends(require_player),
    service: DeckService = Depends(get_deck_service),
) -> DeckListResponse:
    return DeckListResponse(
        items=[_to_deck(deck) for deck in service.list_decks(actor.user_id)]
    )


@router.get(
    "/{deck_id}",
    response_model=DeckOut,
    summary="Consultar uno de mis decks",
    description="Responde 404 tanto si el deck no existe como si es de otro jugador.",
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSE},
)
def get_deck(
    deck_id: str,
    actor: Actor = Depends(require_player),
    service: DeckService = Depends(get_deck_service),
) -> DeckOut:
    return _to_deck(service.get_deck(actor.user_id, deck_id))
