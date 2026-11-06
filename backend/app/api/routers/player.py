"""Participante API del jugador: recibe HTTP y coordina los mensajes 8 y 33–38.

Sesiones identifica al jugador, Colección entrega la recompensa y el componente
de autenticación del gateway emite la credencial interna. Aquí se conectan esas
responsabilidades; sus reglas permanecen en los componentes correspondientes.
"""

import secrets
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request, Response

from app.api.gateway.authentication import TokenIssuer, require_player
from app.api.gateway.errors import AUTH_ERROR_RESPONSES, ErrorResponse
from app.api.schemas.sessions import (
    GoogleChallengeResponse,
    GoogleLoginRequest,
    PlayerResponse,
    SessionResponse,
)
from app.business.collection.initial_collection import InitialCollectionService
from app.business.identity_access.ports import LoginChallengeStore, PlayerRepository
from app.business.identity_access.roles import Actor
from app.business.identity_access.session_service import SessionService
from app.business.shared.errors import (
    IdentityProviderUnavailableError,
    NotAuthenticatedError,
)

router = APIRouter(prefix="/v1", tags=["Jugador"])
CHALLENGE_COOKIE = "pokearena_google_challenge"
SESSION_ERRORS = {
    400: {"model": ErrorResponse, "description": "Solicitud mal formada."},
    401: {"model": ErrorResponse, "description": "Identidad o desafío inválido."},
    503: {
        "model": ErrorResponse,
        "description": "Proveedor o dependencia no disponible.",
    },
}


def get_session_service(request: Request) -> SessionService:
    """Obtiene el servicio de Identidad y Acceso."""
    return request.app.state.session_service


def get_initial_collection_service(request: Request) -> InitialCollectionService:
    """Obtiene el servicio independiente de Colección y Mazos."""
    return request.app.state.initial_collection_service


def get_players(request: Request) -> PlayerRepository:
    """Obtiene el puerto de jugadores para consultar el saldo actualizado."""
    return request.app.state.players


def get_challenges(request: Request) -> LoginChallengeStore:
    """Obtiene los desafíos compartidos por todas las instancias."""
    return request.app.state.login_challenges


def get_token_issuer(request: Request) -> TokenIssuer:
    """Obtiene el emisor propio del gateway."""
    return request.app.state.token_issuer


@router.get(
    "/sesiones/google/desafio",
    response_model=GoogleChallengeResponse,
    summary="Preparar un inicio de sesión de Google de un solo uso",
    responses={503: SESSION_ERRORS[503]},
)
def create_google_challenge(
    request: Request,
    response: Response,
    challenges: LoginChallengeStore = Depends(get_challenges),
) -> GoogleChallengeResponse:
    """Prepara el nonce que vincula el token de Google al navegador solicitante.

    Es una protección adicional al flujo numerado: todavía no autentica ni crea
    al jugador. El POST consumirá este desafío una sola vez.
    """
    settings = request.app.state.settings
    if not settings.google_client_id:
        raise IdentityProviderUnavailableError(
            "El inicio de sesión con Google todavía no está configurado."
        )
    nonce = secrets.token_urlsafe(32)
    challenges.create(nonce, settings.login_challenge_seconds)
    response.set_cookie(
        CHALLENGE_COOKIE,
        nonce,
        max_age=settings.login_challenge_seconds,
        httponly=True,
        secure=settings.environment != "development",
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return GoogleChallengeResponse(
        client_id=settings.google_client_id,
        nonce=nonce,
        expires_in=settings.login_challenge_seconds,
    )


@router.post(
    "/sesiones/google",
    response_model=SessionResponse,
    summary="Iniciar sesión con un token de identidad de Google",
    description=(
        "Ruta pública: verifica Google, identifica al jugador, intenta entregar "
        "su colección y devuelve credenciales propias de corta duración."
    ),
    responses=SESSION_ERRORS,
)
def sign_in_google(
    body: GoogleLoginRequest,
    request: Request,
    response: Response,
    sessions: SessionService = Depends(get_session_service),
    collections: InitialCollectionService = Depends(get_initial_collection_service),
    players: PlayerRepository = Depends(get_players),
    challenges: LoginChallengeStore = Depends(get_challenges),
    issuer: TokenIssuer = Depends(get_token_issuer),
) -> SessionResponse:
    """Atiende la ruta pública del mensaje 6 y coordina el flujo de acceso."""
    nonce = request.cookies.get(CHALLENGE_COOKIE, "")
    origin = request.headers.get("origin")
    if (
        (origin and origin != request.app.state.settings.public_app_url.rstrip("/"))
        or not nonce
        or len(nonce) > 128
        or not challenges.consume(nonce)
    ):
        raise NotAuthenticatedError(
            "El intento de inicio de sesión venció. Inténtalo de nuevo."
        )
    # Mensajes 8 y 33: solo una identidad verificada permite obtener al jugador.
    # Los errores interrumpen aquí el flujo antes de entregar o emitir credenciales.
    player = sessions.sign_in(body.credential, nonce)
    # Mensajes 34–35: la API invoca Colección, responsabilidad de su propia HU.
    # Su resultado pendiente/no disponible se comunica junto al acceso exitoso.
    delivery = collections.deliver(player.id)
    # El saldo puede haber cambiado durante la entrega.
    player = players.get(player.id)
    # Mensajes 36–37: el emisor del gateway recibe la identidad interna y su rol.
    credential = issuer.issue(player)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.delete_cookie(CHALLENGE_COOKIE)
    # Mensaje 38: la app recibe JWT propio, cuenta y estado de la entrega.
    return SessionResponse(
        **asdict(credential),
        player=asdict(player),
        initial_collection=asdict(delivery),
    )


@router.get(
    "/jugadores/yo",
    response_model=PlayerResponse,
    summary="Consultar mi cuenta de jugador",
    responses={**AUTH_ERROR_RESPONSES, 503: {"model": ErrorResponse}},
)
def get_my_player(
    actor: Actor = Depends(require_player),
    players: PlayerRepository = Depends(get_players),
) -> PlayerResponse:
    """Consulta exclusivamente la cuenta identificada por el JWT de Poké-Arena."""
    return PlayerResponse(**asdict(players.get(actor.user_id)))
