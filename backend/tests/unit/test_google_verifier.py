"""Firmas reales, caché, rotación y fallos del transporte de claves."""

from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.api.gateway.google_verifier import GoogleTokenVerifier
from app.business.shared.errors import (
    IdentityProviderUnavailableError,
    NotAuthenticatedError,
)
from tests.google_helpers import GoogleKeysResponse, google_token, public_jwk


@pytest.fixture
def key() -> rsa.RSAPrivateKey:
    """Genera la clave de una autoridad de pruebas efímera."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_keys_are_cached_only_within_google_cache_lifetime(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    """Una clave vigente permite verificar sin otra llamada al proveedor."""
    transport = Mock(
        side_effect=lambda *_args, **_kwargs: GoogleKeysResponse([public_jwk(key)])
    )
    monkeypatch.setattr("app.api.gateway.google_verifier.urlopen", transport)
    verifier = GoogleTokenVerifier("test-client.apps.googleusercontent.com")
    token = google_token(key, "nonce")
    verifier.verify(token, "nonce")
    verifier.verify(token, "nonce")
    assert transport.call_count == 1
    assert verifier._keys.jwk_set_cache.lifespan <= 300


def test_expired_keys_are_not_reused_during_google_outage(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    """No hay caché permanente por kid que permita usar claves expiradas."""
    transport = Mock(
        side_effect=lambda *_args, **_kwargs: GoogleKeysResponse(
            [public_jwk(key)], max_age=0
        )
    )
    monkeypatch.setattr("app.api.gateway.google_verifier.urlopen", transport)
    verifier = GoogleTokenVerifier("test-client.apps.googleusercontent.com")
    token = google_token(key, "nonce")
    verifier.verify(token, "nonce")
    transport.side_effect = TimeoutError()
    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(token, "nonce")


def test_rotated_key_is_refetched_and_signature_verified(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    """Un kid nuevo provoca una actualización con las claves vigentes."""
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    transport = Mock(
        side_effect=[
            GoogleKeysResponse([public_jwk(key)]),
            GoogleKeysResponse([public_jwk(rotated, "rotated")]),
        ]
    )
    monkeypatch.setattr("app.api.gateway.google_verifier.urlopen", transport)
    verifier = GoogleTokenVerifier("test-client.apps.googleusercontent.com")
    original = google_token(key, "nonce")
    verifier.verify(original, "nonce")
    claims = jwt.decode(
        original,
        key.public_key(),
        algorithms=["RS256"],
        audience="test-client.apps.googleusercontent.com",
    )
    token = jwt.encode(claims, rotated, algorithm="RS256", headers={"kid": "rotated"})
    assert verifier.verify(token, "nonce").subject == claims["sub"]
    assert transport.call_count == 2


def test_missing_signing_key_rejects_token_after_refresh(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    """Un kid desconocido en un JWKS válido no se confunde con una caída."""
    monkeypatch.setattr(
        "app.api.gateway.google_verifier.urlopen",
        lambda *_args, **_kwargs: GoogleKeysResponse([public_jwk(key, "other")]),
    )
    with pytest.raises(NotAuthenticatedError):
        GoogleTokenVerifier("test-client.apps.googleusercontent.com").verify(
            google_token(key, "nonce"), "nonce"
        )


def test_unusable_jwks_is_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    """Un proveedor sin claves utilizables responde 503, no token inválido."""
    monkeypatch.setattr(
        "app.api.gateway.google_verifier.urlopen",
        lambda *_args, **_kwargs: GoogleKeysResponse([]),
    )
    with pytest.raises(IdentityProviderUnavailableError):
        GoogleTokenVerifier("test-client.apps.googleusercontent.com").verify(
            google_token(key, "nonce"), "nonce"
        )


@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "iss", "aud", "nonce"])
def test_required_claims_cannot_be_omitted(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey, claim: str
) -> None:
    """Una firma válida no basta si falta un claim obligatorio."""
    monkeypatch.setattr(
        "app.api.gateway.google_verifier.urlopen",
        lambda *_args, **_kwargs: GoogleKeysResponse([public_jwk(key)]),
    )
    claims = jwt.decode(
        google_token(key, "nonce"),
        key.public_key(),
        algorithms=["RS256"],
        audience="test-client.apps.googleusercontent.com",
    )
    del claims[claim]
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(NotAuthenticatedError):
        GoogleTokenVerifier("test-client.apps.googleusercontent.com").verify(
            token, "nonce"
        )
