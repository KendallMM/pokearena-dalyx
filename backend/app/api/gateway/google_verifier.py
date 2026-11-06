"""Participante Verificador de Google: mensajes 9–22 del diagrama.

Google es el sistema externo que firma la identidad. Este adaptador comprueba
esa firma y devuelve una identidad verificada; Sesiones decide qué cuenta usar.
"""

import json
import re
import threading
from typing import Any
from urllib.request import Request, urlopen

import jwt
from jwt.jwk_set_cache import JWKSetCache

from app.business.identity_access.models import ExternalIdentity
from app.business.shared.errors import (
    IdentityProviderUnavailableError,
    NotAuthenticatedError,
)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]


class GoogleJwkClient(jwt.PyJWKClient):
    """Respeta Cache-Control y no usa claves vencidas ante un fallo de red."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(GOOGLE_JWKS_URL, cache_keys=False, timeout=timeout_seconds)

    def fetch_data(self) -> dict[str, Any]:
        """Mensajes 10 y 16: obtiene claves vigentes del origen fijo de Google."""
        try:
            with urlopen(Request(GOOGLE_JWKS_URL), timeout=self.timeout) as response:
                data = json.load(response)
                if not isinstance(data, dict):
                    raise ValueError("Formato de claves públicas inválido")
                key_set = jwt.PyJWKSet.from_dict(data)
                if not any(
                    key.key_type == "RSA" and key.public_key_use in (None, "sig")
                    for key in key_set.keys
                ):
                    raise ValueError("No hay claves de firma")
                cache_control = response.headers.get("Cache-Control", "")
                match = re.search(
                    r"(?:^|,)\s*max-age=(\d+)",
                    cache_control,
                    re.IGNORECASE,
                )
                age = max(0, int(response.headers.get("Age", "0")))
                lifetime = max(0, min(300, int(match[1]) - age)) if match else 0
                if re.search(
                    r"(?:^|,)\s*(?:no-store|no-cache)(?:,|$)",
                    cache_control,
                    re.IGNORECASE,
                ):
                    lifetime = 0
                self.jwk_set_cache = JWKSetCache(lifetime) if lifetime else None
                if self.jwk_set_cache is not None:
                    self.jwk_set_cache.put(data)
                return data
        except (OSError, ValueError, TypeError, KeyError, jwt.PyJWTError) as exc:
            # Break, mensajes 11–15: no poder verificar por falta de claves es 503.
            # El mensaje público y los logs nunca contienen el token ni la respuesta.
            raise IdentityProviderUnavailableError(
                "Google no está disponible para verificar tu identidad. Inténtalo de nuevo."
            ) from exc


class GoogleTokenVerifier:
    """Adaptador del puerto IdentityVerifier; no crea cuentas ni sesiones."""

    def __init__(self, client_id: str, timeout_seconds: float = 5) -> None:
        self._client_id = client_id
        self._keys = GoogleJwkClient(timeout_seconds)
        self._key_lock = threading.Lock()

    def verify(self, credential: str, nonce: str) -> ExternalIdentity:
        """Verifica RS256, emisor, audiencia, tiempos y nonce de un solo uso."""
        if not self._client_id:
            raise IdentityProviderUnavailableError(
                "El inicio de sesión con Google todavía no está configurado."
            )
        try:
            if len(credential) > 16384:
                raise jwt.InvalidTokenError()
            # Se lee solo la cabecera para elegir la clave; esto aún no autentica.
            header = jwt.get_unverified_header(credential)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise jwt.InvalidTokenError()
            with self._key_lock:
                key = self._keys.get_signing_key_from_jwt(credential)
            # Mensaje 17: decode verifica realmente firma, tiempos, emisor y audiencia.
            # El algoritmo permitido es fijo; el token recibido no puede elegirlo.
            claims = jwt.decode(
                credential,
                key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=GOOGLE_ISSUERS,
                options={"require": ["sub", "iss", "aud", "exp", "iat", "nonce"]},
            )
            self._validate_identity(claims, nonce)
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            # Alt, mensajes 18–21: identidad inválida produce 401, sin crear cuenta.
            raise NotAuthenticatedError(
                "La identidad de Google no es válida o ya venció. Inicia sesión de nuevo."
            ) from exc
        # Mensaje 22: solo los datos ya verificados pasan al Servicio de Sesiones.
        return ExternalIdentity(
            provider="google",
            subject=claims["sub"],
            email=claims["email"],
            name=str(claims.get("name") or "Jugador")[:100],
        )

    def _validate_identity(self, claims: dict[str, Any], nonce: str) -> None:
        """Exige identidad estable y coherencia del destinatario autorizado."""
        subject = claims["sub"]
        audience = claims["aud"]
        authorized_party = claims.get("azp")
        if (
            not isinstance(subject, str)
            or not 1 <= len(subject) <= 255
            or not isinstance(claims.get("email"), str)
            or not 1 <= len(claims["email"]) <= 320
            or claims.get("email_verified") is not True
            or claims["nonce"] != nonce
            or (authorized_party is not None and authorized_party != self._client_id)
            or (
                isinstance(audience, list)
                and len(audience) > 1
                and not authorized_party
            )
        ):
            raise jwt.InvalidTokenError()
