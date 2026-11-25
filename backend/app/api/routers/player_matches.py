"""Consulta del estado inicial de una partida del jugador."""

from fastapi import APIRouter, Depends, Request, Response

from app.api.gateway.authentication import require_player
from app.api.gateway.errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE
from app.api.schemas.player_matches import InitialMatchResponse
from app.business.identity_access.roles import Actor
from app.business.shared.errors import ServiceUnavailableError

router = APIRouter(prefix="/v1/partidas", tags=["Jugador"])


@router.get(
    "/{match_id}",
    response_model=InitialMatchResponse,
    summary="Consultar el estado inicial de una partida",
    description="Solo los participantes pueden consultar la partida y cada uno recibe su propia mano.",
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSE},
)
def initial_match(
    match_id: str,
    request: Request,
    response: Response,
    actor: Actor = Depends(require_player),
):
    matches = request.app.state.match_service
    if matches is None:
        raise ServiceUnavailableError("La consulta de partidas no está disponible.")
    response.headers["Cache-Control"] = "private, no-store"
    return matches.initial_view(match_id, actor.user_id)


@router.get(
    "/{match_id}/ubicaciones/{location_id}/imagen",
    summary="Ver la imagen de una ubicación de la partida",
    response_class=Response,
    responses={
        200: {"content": {"image/*": {}}, "description": "La imagen."},
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
    },
)
def match_location_image(
    match_id: str,
    location_id: int,
    request: Request,
    actor: Actor = Depends(require_player),
) -> Response:
    matches = request.app.state.match_service
    if matches is None:
        raise ServiceUnavailableError("La consulta de partidas no está disponible.")
    image_id = matches.location_image_id(match_id, actor.user_id, location_id)
    image = request.app.state.location_service.match_image(image_id)
    return Response(
        content=image.data,
        media_type=image.content_type,
        headers={"Cache-Control": "private, no-store"},
    )
