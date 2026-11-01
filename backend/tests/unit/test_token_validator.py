"""Validación del JWT: firma, vencimiento, emisor, audiencia, campos y algoritmo."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.api.gateway.authentication import TokenValidator
from app.business.identity_access.roles import Role
from app.business.shared.errors import NotAuthenticatedError
from tests.conftest import SECRET


def test_valid_token_returns_actor(validator, make_token) -> None:
    actor = validator.validate(make_token(role="content_admin"))
    assert actor.user_id == "user-1"
    assert actor.role is Role.CONTENT_ADMIN


def test_expired_token_is_rejected(validator, make_token) -> None:
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(NotAuthenticatedError):
        validator.validate(make_token(exp=expired))


def test_wrong_signature_is_rejected(validator, settings) -> None:
    token = jwt.encode(
        {
            "sub": "u",
            "role": "content_admin",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "otra-clave-distinta-de-al-menos-32-caracteres",
        algorithm="HS256",
    )
    with pytest.raises(NotAuthenticatedError):
        validator.validate(token)


@pytest.mark.parametrize("claim", ["iss", "aud", "sub", "exp"])
def test_missing_required_claim_is_rejected(validator, make_token, claim) -> None:
    token = make_token(**{claim: None})
    with pytest.raises(NotAuthenticatedError):
        validator.validate(token)


def test_wrong_issuer_or_audience_is_rejected(validator, make_token) -> None:
    with pytest.raises(NotAuthenticatedError):
        validator.validate(make_token(iss="otro"))
    with pytest.raises(NotAuthenticatedError):
        validator.validate(make_token(aud="otro"))


def test_unknown_or_missing_role_is_rejected(validator, make_token) -> None:
    with pytest.raises(NotAuthenticatedError):
        validator.validate(make_token(role="superuser"))
    with pytest.raises(NotAuthenticatedError):
        validator.validate(make_token(role=None))


def test_algorithm_is_chosen_by_server_not_by_token(settings) -> None:
    """Un token firmado con un algoritmo no permitido se rechaza."""
    validator = TokenValidator(
        SECRET, ["HS256"], settings.jwt_issuer, settings.jwt_audience
    )
    token = jwt.encode(
        {
            "sub": "u",
            "role": "content_admin",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS512",
    )
    with pytest.raises(NotAuthenticatedError):
        validator.validate(token)


def test_unsigned_token_is_rejected(validator) -> None:
    token = jwt.encode({"sub": "u", "role": "content_admin"}, None, algorithm="none")
    with pytest.raises(NotAuthenticatedError):
        validator.validate(token)
