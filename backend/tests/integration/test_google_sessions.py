"""El endpoint usa verificación criptográfica y persistencia reales."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import Mock
from typing import Any
from uuid import uuid4

import fakeredis
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from app.api.gateway.authentication import TokenIssuer
from app.api.gateway.google_verifier import GoogleTokenVerifier
from app.api.routers.player import CHALLENGE_COOKIE
from app.business.collection.initial_collection import (
    STARTER_CARD_COUNT,
    STARTER_CUBES,
)
from app.business.identity_access.models import ExternalIdentity, Player
from app.business.identity_access.session_service import SessionService
from app.persistence.cache.login_challenges import RedisLoginChallengeStore
from app.persistence.relational.models import (
    CardRow,
    CubeMovementRow,
    ExternalIdentityRow,
    InitialCollectionDeliveryRow,
    PlayerCardRow,
    PlayerRow,
    RarityRow,
)
from app.persistence.relational.player_repository import SqlPlayerRepository
from tests.builders import real_initial_collection_service
from tests.google_helpers import GoogleKeysResponse, google_token, public_jwk


@pytest.fixture(scope="module")
def google_key() -> rsa.RSAPrivateKey:
    """Una clave efímera; nunca se guarda material privado en el repositorio."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def google_transport(
    monkeypatch: pytest.MonkeyPatch, google_key: rsa.RSAPrivateKey
) -> Mock:
    """Reemplaza únicamente el transporte HTTP, no la validación de firma."""
    transport = Mock(
        side_effect=lambda *_args, **_kwargs: GoogleKeysResponse(
            [public_jwk(google_key)]
        )
    )
    monkeypatch.setattr("app.api.gateway.google_verifier.urlopen", transport)
    return transport


def add_cards(
    session_factory: sessionmaker[Session],
    prefix: str,
    count: int,
    rarity_code: str = "COMMON",
    status: str = "available",
) -> list[int]:
    """Agrega cartas al catálogo de la base de prueba y devuelve sus ids."""
    with session_factory.begin() as session:
        rarity_id = session.scalar(
            select(RarityRow.id).where(RarityRow.code == rarity_code)
        )
        rows = [
            CardRow(
                code=f"{prefix}-{index:03}",
                name=f"{prefix} {index}",
                search_name=f"{prefix} {index}".lower(),
                cost=1,
                power=1,
                card_type_id=1,
                rarity_id=rarity_id,
                ability_id=1,
                image_id=str(uuid4()),
                status=status,
            )
            for index in range(count)
        ]
        session.add_all(rows)
        session.flush()
        return [row.id for row in rows]


@pytest.fixture
def common_card_ids(session_factory: sessionmaker[Session]) -> list[int]:
    """Más Comunes de las necesarias, y cartas que nunca deben entregarse."""
    commons = add_cards(session_factory, "COM", STARTER_CARD_COUNT + 5)
    add_cards(session_factory, "RAR", 20, rarity_code="RARE")
    add_cards(session_factory, "PND", 5, status="pending_thumbnail")
    return commons


def assert_starter_collection(
    session_factory: sessionmaker[Session],
    player_id: str,
    common_ids: list[int],
) -> None:
    """15 Comunes distintas y disponibles, 1,000 cubos y un solo movimiento."""
    with session_factory() as session:
        owned = session.scalars(
            select(PlayerCardRow).where(PlayerCardRow.player_id == player_id)
        ).all()
        assert len(owned) == STARTER_CARD_COUNT
        assert all(row.quantity == 1 for row in owned)
        assert {row.card_id for row in owned} <= set(common_ids)
        assert session.get(PlayerRow, player_id).cubes == STARTER_CUBES
        movements = session.scalars(
            select(CubeMovementRow)
            .where(CubeMovementRow.player_id == player_id)
            .order_by(CubeMovementRow.id)
        ).all()
        assert len(movements) == 1
        first = movements[0]
        assert first.amount == STARTER_CUBES
        assert first.balance_after == STARTER_CUBES
        assert first.reason == "initial_collection"


def assert_nothing_granted(session_factory: sessionmaker[Session]) -> None:
    """La cuenta existe, pero sin cartas, cubos ni movimientos."""
    with session_factory() as session:
        assert session.scalars(select(PlayerRow)).one().cubes == 0
        assert session.scalar(select(func.count()).select_from(PlayerCardRow)) == 0
        assert session.scalar(select(func.count()).select_from(CubeMovementRow)) == 0
        assert (
            session.scalars(select(InitialCollectionDeliveryRow)).one().status
            == "pending"
        )


def set_status(
    session_factory: sessionmaker[Session], card_id: int, status: str
) -> None:
    with session_factory.begin() as session:
        session.get(CardRow, card_id).status = status


@pytest.fixture
def login_app(
    client: TestClient,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
    google_transport: Mock,
) -> FastAPI:
    """Reutiliza la composición existente y añade los servicios de sesión reales."""
    app = client.app
    settings = app.state.settings.model_copy(
        update={
            "google_client_id": "test-client.apps.googleusercontent.com",
            "jwt_expiration_minutes": 15,
        }
    )
    app.state.settings = settings
    app.state.players = SqlPlayerRepository(session_factory)
    app.state.session_service = SessionService(
        GoogleTokenVerifier(settings.google_client_id),
        app.state.players,
    )
    app.state.initial_collection_service = real_initial_collection_service(
        session_factory
    )
    app.state.login_challenges = RedisLoginChallengeStore(fakeredis.FakeRedis())
    app.state.token_issuer = TokenIssuer(
        settings.jwt_secret,
        settings.jwt_issuer,
        settings.jwt_audience,
        15,
    )
    return app


def sign_in(
    client: TestClient, key: rsa.RSAPrivateKey, **claims: Any
) -> httpx.Response:
    """Completa el desafío del navegador y el POST público real."""
    challenge = client.get("/v1/sesiones/google/desafio")
    assert challenge.status_code == 200
    token = google_token(key, challenge.json()["nonce"], **claims)
    return client.post("/v1/sesiones/google", json={"credential": token})


def test_first_sign_in_creates_player_and_grants_collection(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """El primer ingreso confirma cuenta, cartas y cubos antes de emitir el JWT interno."""
    with TestClient(login_app) as browser:
        response = sign_in(browser, google_key)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["player"]["role"] == "player"
    assert body["player"]["elo"] == 0
    assert body["player"]["cubes"] == STARTER_CUBES
    assert body["initial_collection"]["status"] == "delivered"
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert response.headers["cache-control"] == "no-store"
    actor = login_app.state.token_validator.validate(body["access_token"])
    assert actor.user_id == body["player"]["id"]
    assert_starter_collection(session_factory, body["player"]["id"], common_card_ids)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerRow)) == 1
        delivery = session.scalars(select(InitialCollectionDeliveryRow)).one()
        assert delivery.status == "delivered"
        assert delivery.cubes_granted == STARTER_CUBES


def test_repeated_login_and_changed_email_reuse_account_and_rewards(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """El identificador estable conserva cuenta y recompensa aunque cambie el correo."""
    with TestClient(login_app) as browser:
        first = sign_in(browser, google_key).json()
        again = sign_in(browser, google_key, email="changed@example.test").json()
    assert again["player"]["id"] == first["player"]["id"]
    assert again["player"]["cubes"] == STARTER_CUBES
    assert again["initial_collection"]["status"] == "already_delivered"
    assert_starter_collection(session_factory, first["player"]["id"], common_card_ids)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerRow)) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"aud": "another-client"},
        {"iss": "https://attacker.example"},
        {"nonce": "wrong-nonce"},
        {"email_verified": False},
        {"sub": ""},
        {"azp": "another-client"},
        {"iat": 9999999999},
        {"aud": ["test-client.apps.googleusercontent.com", "other"]},
    ],
)
def test_invalid_tokens_never_create_partial_accounts(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    overrides: dict[str, Any],
) -> None:
    """Una identidad rechazada no produce cuentas, asociaciones ni solicitudes de entrega."""
    with TestClient(login_app) as browser:
        response = sign_in(browser, google_key, **overrides)
    assert response.status_code == 401, response.text
    assert response.json()["code"] == "not_authenticated"
    assert response.json()["correlation_id"]
    with session_factory() as session:
        for table in (PlayerRow, ExternalIdentityRow, InitialCollectionDeliveryRow):
            assert session.scalar(select(func.count()).select_from(table)) == 0


def test_invalid_signature_never_creates_account(
    login_app: FastAPI, session_factory: sessionmaker[Session]
) -> None:
    """Usar otra clave RSA no permite fabricar una identidad aceptada."""
    another_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with TestClient(login_app) as browser:
        response = sign_in(browser, another_key)
    assert response.status_code == 401
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerRow)) == 0


@pytest.mark.parametrize("credential", ["not-a-jwt", "", "a.b.c"])
def test_malformed_tokens_are_401(login_app: FastAPI, credential: str) -> None:
    """Un token ilegible mantiene el contrato de autenticación 401."""
    with TestClient(login_app) as browser:
        browser.get("/v1/sesiones/google/desafio")
        response = browser.post("/v1/sesiones/google", json={"credential": credential})
    assert response.status_code == 401


def test_google_outage_is_503_with_correlation_without_partial_account(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    google_transport: Mock,
    session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La caída de claves públicas se distingue del token inválido y se puede rastrear."""
    google_transport.side_effect = TimeoutError("provider timed out")
    with TestClient(login_app) as browser:
        challenge = browser.get("/v1/sesiones/google/desafio").json()
        token = google_token(google_key, challenge["nonce"])
        response = browser.post(
            "/v1/sesiones/google",
            json={"credential": token},
            headers={"X-Correlation-ID": "google-outage"},
        )
    assert response.status_code == 503
    assert response.json()["code"] == "identity_provider_unavailable"
    assert response.json()["correlation_id"] == "google-outage"
    assert response.headers["X-Correlation-ID"] == "google-outage"
    assert token not in response.text + caplog.text
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlayerRow)) == 0


def test_internal_credentials_authorize_own_account_and_enforce_role(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
) -> None:
    """El gateway identifica al jugador interno y conserva la autorización por permisos."""
    with TestClient(login_app) as browser:
        result = sign_in(browser, google_key).json()
        headers = {"Authorization": f"Bearer {result['access_token']}"}
        profile = browser.get("/v1/jugadores/yo", headers=headers)
        assert profile.status_code == 200
        assert profile.json() == result["player"]
        assert browser.get("/admin/referencias", headers=headers).status_code == 403
        external_token = google_token(google_key, "external")
        assert (
            browser.get(
                "/v1/jugadores/yo",
                headers={"Authorization": f"Bearer {external_token}"},
            ).status_code
            == 401
        )
        assert browser.get("/v1/jugadores/yo").status_code == 401


def test_challenge_is_one_use_and_rejects_cross_origin(
    login_app: FastAPI, google_key: rsa.RSAPrivateKey
) -> None:
    """El desafío vinculado al navegador no admite otro origen ni una repetición."""
    with TestClient(login_app) as browser:
        challenge = browser.get("/v1/sesiones/google/desafio")
        cookie = browser.cookies.get(CHALLENGE_COOKIE)
        assert "HttpOnly" in challenge.headers["set-cookie"]
        assert "SameSite=strict" in challenge.headers["set-cookie"]
        token = google_token(google_key, challenge.json()["nonce"])
        assert (
            browser.post(
                "/v1/sesiones/google",
                json={"credential": token},
                headers={"Origin": "https://attacker.example"},
            ).status_code
            == 401
        )
        assert (
            browser.post("/v1/sesiones/google", json={"credential": token}).status_code
            == 200
        )
        browser.cookies.set(CHALLENGE_COOKIE, cookie)
        assert (
            browser.post("/v1/sesiones/google", json={"credential": token}).status_code
            == 401
        )


def test_not_enough_commons_creates_account_without_rewards_until_next_login(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """Con menos de 15 Comunes disponibles no se entrega nada; el siguiente ingreso sí."""
    # Deja exactamente 14 Comunes disponibles.
    hidden = common_card_ids[: len(common_card_ids) - STARTER_CARD_COUNT + 1]
    for card_id in hidden:
        set_status(session_factory, card_id, "pending_thumbnail")
    with TestClient(login_app) as browser:
        result = sign_in(browser, google_key).json()
        assert result["initial_collection"]["status"] == "unavailable"
        assert "aún no está disponible" in result["initial_collection"]["message"]
        assert result["player"]["cubes"] == 0
        assert_nothing_granted(session_factory)
        # El catálogo se completa; el siguiente ingreso entrega sin esperar
        # al planificador.
        set_status(session_factory, hidden[0], "available")
        again = sign_in(browser, google_key).json()
    assert again["initial_collection"]["status"] == "delivered"
    assert again["player"]["cubes"] == STARTER_CUBES
    assert_starter_collection(session_factory, result["player"]["id"], common_card_ids)


def test_scheduler_completes_pending_delivery_without_login(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """La solicitud persiste y el planificador la completa respetando la espera."""
    for card_id in common_card_ids:
        set_status(session_factory, card_id, "pending_thumbnail")
    clock = Mock()
    clock.now.return_value = datetime.now(timezone.utc)
    collections = real_initial_collection_service(session_factory, clock=clock)
    login_app.state.initial_collection_service = collections
    with TestClient(login_app) as browser:
        result = sign_in(browser, google_key).json()
    assert result["initial_collection"]["status"] == "unavailable"
    for card_id in common_card_ids:
        set_status(session_factory, card_id, "available")
    # Antes de que venza la espera, el planificador no lo intenta.
    collections.run()
    assert_nothing_granted(session_factory)
    clock.now.return_value = datetime.now(timezone.utc) + timedelta(seconds=61)
    collections.run()
    collections.run()
    assert_starter_collection(session_factory, result["player"]["id"], common_card_ids)


def test_client_data_does_not_influence_delivered_cards(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """Campos extra del cliente se ignoran: cartas y cubos los decide el servidor."""
    with session_factory() as session:
        rare_ids = session.scalars(
            select(CardRow.id).where(CardRow.code.like("RAR-%"))
        ).all()
    with TestClient(login_app) as browser:
        challenge = browser.get("/v1/sesiones/google/desafio").json()
        token = google_token(google_key, challenge["nonce"])
        response = browser.post(
            "/v1/sesiones/google",
            json={
                "credential": token,
                "cards": list(rare_ids),
                "card_ids": list(rare_ids),
                "cubes": 999_999,
                "seed": 42,
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["player"]["cubes"] == STARTER_CUBES
    assert_starter_collection(
        session_factory, response.json()["player"]["id"], common_card_ids
    )


def test_failed_delivery_rolls_back_rewards_and_completes_on_next_login(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """Un fallo al confirmar revierte todo; el siguiente ingreso completa la entrega."""
    engine = session_factory.kw["bind"]

    def fail_grant(
        connection: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        # Falla en el paso 29, cuando la marca y las cartas ya se escribieron.
        if statement.startswith("INSERT INTO cube_movements"):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("grant", {}, Exception("storage unavailable"))

    event.listen(engine, "before_cursor_execute", fail_grant)
    try:
        with TestClient(login_app) as browser:
            response = sign_in(browser, google_key)
        assert response.status_code == 200
        assert response.json()["initial_collection"]["status"] == "pending"
        assert_nothing_granted(session_factory)
    finally:
        event.remove(engine, "before_cursor_execute", fail_grant)
    with TestClient(login_app) as browser:
        again = sign_in(browser, google_key).json()
    assert again["initial_collection"]["status"] == "delivered"
    assert_starter_collection(
        session_factory, response.json()["player"]["id"], common_card_ids
    )


def test_simultaneous_logins_create_exactly_one_account_and_delivery(
    login_app: FastAPI,
    google_key: rsa.RSAPrivateKey,
    session_factory: sessionmaker[Session],
    common_card_ids: list[int],
) -> None:
    """La carrera real de INSERT se resuelve sin cuentas huérfanas ni dobles premios."""
    barrier = Barrier(2)

    class ConcurrentPlayers(SqlPlayerRepository):
        """Fuerza la carrera entre los dos INSERT reales de identidad."""

        def create(self, identity: ExternalIdentity) -> Player:
            barrier.wait(timeout=10)
            return super().create(identity)

    players = ConcurrentPlayers(session_factory)
    login_app.state.players = players
    login_app.state.session_service = SessionService(
        GoogleTokenVerifier(login_app.state.settings.google_client_id),
        players,
    )

    def attempt() -> httpx.Response:
        with TestClient(login_app) as browser:
            return sign_in(browser, google_key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: attempt(), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json()["player"]["id"] == responses[1].json()["player"]["id"]
    with session_factory() as session:
        for table in (PlayerRow, ExternalIdentityRow, InitialCollectionDeliveryRow):
            assert session.scalar(select(func.count()).select_from(table)) == 1
    assert_starter_collection(
        session_factory, responses[0].json()["player"]["id"], common_card_ids
    )
