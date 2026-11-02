"""Autenticación: valida el JWT propio de Poké-Arena y comprueba permisos."""

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.business.identity_access.permissions import Permission, ensure_permission
from app.business.identity_access.roles import Actor, Role
from app.business.shared.errors import NotAuthenticatedError

REQUIRED_CLAIMS = ["exp", "sub", "iss", "aud"]

bearer_scheme = HTTPBearer(auto_error=False, description="JWT de Poké-Arena")


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
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=self._algorithms,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": REQUIRED_CLAIMS},
            )
            role = Role(claims.get("role"))
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
