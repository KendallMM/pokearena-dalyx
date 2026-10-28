import pytest

from tests.api import post_card, post_location
from tests.helpers import JWT_SECRET, auth, make_token


@pytest.mark.parametrize(
    "path",
    [
        "/admin/cartas",
        "/admin/cartas/PKA-FUE-001/estado",
        "/admin/ubicaciones/1/estado",
    ],
)
async def test_requires_token(client, path):
    response = await client.get(path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_error_envelope_shape(client):
    body = (await client.get("/admin/cartas")).json()
    assert set(body["error"]) == {"code", "message", "field", "details"}


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        make_token(secret="otra-clave-otra-clave-otra-clave-1234"),
        make_token(role=None),
        make_token(algorithm="HS512"),
    ],
)
async def test_invalid_tokens_are_401(client, token):
    response = await client.get("/admin/cartas", headers=auth(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_expired_token(client):
    response = await client.get(
        "/admin/cartas", headers=auth(make_token(expires_in=-10))
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


async def test_unsigned_none_algorithm_rejected(client):
    import base64
    import json

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = b64({"alg": "none", "typ": "JWT"})
    claims = b64({"sub": "a", "role": "admin", "exp": 9999999999})
    token = f"{header}.{claims}."
    response = await client.get("/admin/cartas", headers=auth(token))
    assert response.status_code == 401


async def test_non_bearer_scheme(client):
    response = await client.get(
        "/admin/cartas", headers={"Authorization": f"Basic {make_token()}"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["user", "player", "Admin", ""])
async def test_non_admin_is_403(client, role):
    response = await client.get("/admin/cartas", headers=auth(make_token(role=role)))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


async def test_auth_checked_before_validation(client):
    # Cuerpo inválido y sin token: debe ganar el 401, no el 400.
    r = await client.post("/admin/cartas", data={"cost": "abc"})
    assert r.status_code == 401
    r = await client.post(
        "/admin/cartas", data={"cost": "abc"}, headers=auth(make_token(role="user"))
    )
    assert r.status_code == 403
    r = await client.post("/admin/ubicaciones", data={"card_limit": "abc"})
    assert r.status_code == 401


async def test_post_without_token_creates_nothing(client, container, no_background):
    from tests.api import all_cards

    response = await post_card(client, headers={})
    assert response.status_code == 401
    assert await all_cards(container) == []
    response = await post_location(client, headers={})
    assert response.status_code == 401


async def test_issuer_and_audience_enforced(container):
    import dataclasses

    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    settings = dataclasses.replace(
        container.settings, jwt_issuer="poke", jwt_audience="backoffice"
    )
    container.settings = settings
    app = create_app(settings)
    app.state.container = container
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        ok = make_token(iss="poke", aud="backoffice")
        assert (await c.get("/admin/cartas", headers=auth(ok))).status_code == 200
        for bad in (
            make_token(),
            make_token(iss="x", aud="backoffice"),
            make_token(iss="poke", aud="otro"),
        ):
            assert (await c.get("/admin/cartas", headers=auth(bad))).status_code == 401


def test_secret_constant_is_long_enough():
    assert len(JWT_SECRET) >= 32
