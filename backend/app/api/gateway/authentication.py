"""Participante API Gateway: emite credenciales en el mensaje 37 y las autoriza.

La emisión y validación usan identidad y rol internos de Poké-Arena. Las siguientes
solicitudes se validan aquí sin volver a consultar al proveedor externo.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.business.identity_access.permissions import Permission, ensure_permission
from app.business.identity_access.roles import Actor, Role
from app.business.identity_access.models import Player
from app.business.shared.errors import NotAuthenticatedError

REQUIRED_CLAIMS = ["exp", "sub", "iss", "aud"]

bearer_scheme = HTTPBearer(auto_error=False, description="JWT de Poké-Arena")


@dataclass(frozen=True)
class AccessCredential:
    """Credencial interna de corta duración, sin datos del proveedor."""

    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime


class TokenIssuer:
    """Emite JWT propios en el gateway usando la firma interna existente."""

    def __init__(
        self, secret: str, issuer: str, audience: str, expiration_minutes: int
    ) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._lifetime = timedelta(minutes=expiration_minutes)

    def issue(self, player: Player) -> AccessCredential:
        """Representa al jugador interno y su rol, con vencimiento configurable."""
        now = datetime.now(timezone.utc)
        expires_at = now + self._lifetime
        # Mensaje 37: sub es el ID de players, distinto del sub externo de Google.
        # El rol procede de la cuenta persistida y define los permisos posteriores.
        token = jwt.encode(
            {
                "sub": player.id,
                "role": player.role.value,
                "iss": self._issuer,
                "aud": self._audience,
                "iat": now,
                "exp": expires_at,
            },
            self._secret,
            algorithm="HS256",
        )
        return AccessCredential(
            token, "Bearer", int(self._lifetime.total_seconds()), expires_at
        )


class TokenValidator:
    """Valida tokens JWT. Los algoritmos permitidos vienen de la configuración."""

    def __init__(
        self, secret: str, algorithms: list[str], issuer: str, audience: str
    ) -> None:
        self._secret = secret
        self._algorithms = algorithms
        self._issuer = issuer
        self._audience = audience

    def validate(self, token: str) -> Actor:
        """Devuelve el actor del token o lanza NotAuthenticatedError."""
        try:
            # Nota final del diagrama: la firma, emisor y audiencia exigidos son
            # los propios; presentar directamente un ID token de Google no autoriza.
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=self._algorithms,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": REQUIRED_CLAIMS},
            )
            role = Role(claims.get("role"))
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise jwt.InvalidTokenError()
        except (jwt.PyJWTError, ValueError) as exc:
            raise NotAuthenticatedError("La sesión no es válida o ya venció.") from exc
        return Actor(user_id=str(claims["sub"]), role=role)


def get_token_validator(request: Request) -> TokenValidator:
    """Obtiene el validador armado al iniciar la aplicación."""
    return request.app.state.token_validator


def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    validator: TokenValidator = Depends(get_token_validator),
) -> Actor:
    """Identifica al usuario. Sin credenciales o con token inválido: 401."""
    if credentials is None:
        raise NotAuthenticatedError("Debe iniciar sesión para realizar esta operación.")
    return validator.validate(credentials.credentials)


def require_content_admin(actor: Actor = Depends(get_current_actor)) -> Actor:
    """Exige un administrador de contenido. Sin permiso: 403."""
    ensure_permission(actor, Permission.MANAGE_CATALOG)
    return actor


def require_player(actor: Actor = Depends(get_current_actor)) -> Actor:
    """Autoriza la API del jugador con credenciales internas y su permiso."""
    ensure_permission(actor, Permission.PLAY)
    return actor
