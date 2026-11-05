"""Firmas RSA reales y transporte de Google simulado solo para pruebas."""

import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


class GoogleKeysResponse(io.BytesIO):
    """Respuesta HTTP de claves públicas sin acceso a Google."""

    def __init__(self, keys: list[dict[str, Any]], max_age: int = 3600) -> None:
        super().__init__(json.dumps({"keys": keys}).encode())
        self.headers = {"Cache-Control": f"public, max-age={max_age}", "Age": "0"}


def public_jwk(private_key: rsa.RSAPrivateKey, kid: str = "test-key") -> dict[str, Any]:
    """Publica únicamente la parte pública de la clave generada para la prueba."""
    return {
        **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())),
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
    }


def google_token(
    private_key: rsa.RSAPrivateKey,
    challenge_nonce: str,
    **overrides: Any,
) -> str:
    """Firma una identidad de prueba con tiempos, audiencia y nonce reales."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "google-player-123",
        "iss": "https://accounts.google.com",
        "aud": "test-client.apps.googleusercontent.com",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "nonce": challenge_nonce,
        "email": "player@example.test",
        "email_verified": True,
        "name": "Jugador",
        **overrides,
    }
    return jwt.encode(
        claims, private_key, algorithm="RS256", headers={"kid": "test-key"}
    )
