"""POST y GET /v1/mazos con la base migrada. Historia Crear un deck."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import mongomock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.content.cards.card_directory import CardDirectory
from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.collection.decks import DeckNameConflictError, DeckService
from app.business.image_processing.image_processor import ImageProcessor
from app.composition import Container
from app.main import create_app
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.card_search_repository import SqlCardSearchRepository
from app.persistence.relational.collection_repository import SqlCollectionRepository
from app.persistence.relational.deck_repository import SqlDeckRepository
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.models import (
    CardRow,
    DeckCardRow,
    DeckRow,
    InitialCollectionDeliveryRow,
    PlayerCardRow,
    PlayerRow,
)
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_initial_collection_service, real_search_service
from tests.fakes import InMemoryIdempotencyStore

PLAYER = "user-1"
RIVAL = "user-2"


@pytest.fixture
def api(settings, validator, session_factory: sessionmaker[Session]) -> TestClient:
    images = mongomock.MongoClient().db["images"]
    store = MongoImageStore(images)
    references = ReferenceService(SqlReferenceRepository(session_factory))
    app = create_app(
        Container(
            settings,
            validator,
            InMemoryIdempotencyStore(),
            references,
            CardService(
                references,
                ImageProcessor(),
                store,
                SqlCardRepository(session_factory),
                SystemClock(),
            ),
            LocationService(
                references,
                ImageProcessor(),
                store,
                SqlLocationRepository(session_factory),
                SystemClock(),
            ),
            real_search_service(session_factory, images, references),
            deck_service=DeckService(
                SqlDeckRepository(session_factory),
                CardDirectory(SqlCardSearchRepository(session_factory)),
                SqlCollectionRepository(session_factory),
            ),
        )
    )
    return TestClient(app)


@pytest.fixture
def codes(session_factory: sessionmaker[Session]) -> list[str]:
    """14 cartas: el jugador posee las primeras 13 y el rival todas."""
    with session_factory.begin() as session:
        session.add_all(
            [
                PlayerRow(id=PLAYER, name="Ash", email="ash@x.test"),
                PlayerRow(id=RIVAL, name="Gary", email="gary@x.test"),
            ]
        )
        rows = [
            CardRow(
                code=f"TST-{i:03}",
                name=f"Carta {i}",
                search_name=f"carta {i}",
                cost=1,
                power=2,
                card_type_id=1,
                rarity_id=1,
                ability_id=1,
                image_id=f"image-{i}",
                status="available",
            )
            for i in range(1, 15)
        ]
        session.add_all(rows)
        session.flush()
        session.add_all(
            [PlayerCardRow(player_id=PLAYER, card_id=r.id) for r in rows[:13]]
            + [PlayerCardRow(player_id=RIVAL, card_id=r.id) for r in rows]
        )
        return [row.code for row in rows]


@pytest.fixture
def auth(make_token):
    def _auth(player: str = PLAYER, key: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {make_token(role='player', sub=player)}"}
        if key:
            headers["Idempotency-Key"] = key
        return headers

    return _auth


def post(api, auth, name, cards, key="op-1", player=PLAYER):
    return api.post(
        "/v1/mazos",
        json={"name": name, "cards": cards},
        headers=auth(player, key),
    )


def count_decks(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(DeckRow))


def test_requires_a_player_session(api, make_token) -> None:
    assert api.get("/v1/mazos").status_code == 401
    admin = {"Authorization": f"Bearer {make_token(role='content_admin')}"}
    assert api.get("/v1/mazos", headers=admin).status_code == 403
    assert (
        api.post("/v1/mazos", json={"name": "x", "cards": []}, headers=admin)
    ).status_code == 403


def test_create_and_read_my_decks(api, auth, codes, session_factory) -> None:
    response = post(api, auth, "  Fuego   Rojo ", codes[:12])
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["name"] == "Fuego Rojo"
    assert created["card_codes"] == codes[:12]
    assert post(api, auth, "Otro", codes[1:13], key="op-2").status_code == 201

    listed = api.get("/v1/mazos", headers=auth()).json()["items"]
    assert {deck["name"] for deck in listed} == {"Fuego Rojo", "Otro"}
    assert all(len(deck["cards"]) == 12 for deck in listed)

    detail = api.get(f"/v1/mazos/{created['id']}", headers=auth()).json()
    assert [card["code"] for card in detail["cards"]] == codes[:12]
    first = detail["cards"][0]
    assert first["image_url"] == f"/v1/cartas/{codes[0]}/imagen"
    assert first["card_type"]["code"] and first["rarity"]["code"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(DeckCardRow)) == 24


def test_empty_list_when_the_player_has_no_decks(api, auth, codes) -> None:
    assert api.get("/v1/mazos", headers=auth()).json() == {"items": []}


@pytest.mark.parametrize("count", [11, 13])
def test_wrong_count_is_rejected(api, auth, codes, session_factory, count) -> None:
    response = post(api, auth, "Deck", (codes * 2)[:count])
    assert response.status_code == 400
    assert response.json()["field"] == "cards"
    assert f"tiene {count}" in response.json()["message"]
    assert count_decks(session_factory) == 0


def test_repeated_cards_are_rejected(api, auth, codes, session_factory) -> None:
    response = post(api, auth, "Deck", codes[:11] + [codes[0]])
    assert response.status_code == 400
    assert codes[0] in response.json()["message"]
    assert count_decks(session_factory) == 0


def test_unowned_card_is_rejected(api, auth, codes, session_factory) -> None:
    response = post(api, auth, "Deck", codes[:11] + [codes[13]])
    assert response.status_code == 400
    assert codes[13] in response.json()["message"]
    assert count_decks(session_factory) == 0


def test_missing_operation_id_is_rejected(api, auth, codes) -> None:
    response = api.post(
        "/v1/mazos", json={"name": "Deck", "cards": codes[:12]}, headers=auth()
    )
    assert response.status_code == 400
    assert response.json()["field"] == "Idempotency-Key"


def test_network_retry_does_not_duplicate(api, auth, codes, session_factory) -> None:
    first = post(api, auth, "Deck", codes[:12])
    again = post(api, auth, "Deck", codes[:12])
    assert again.status_code == 201
    assert again.json() == first.json()
    assert again.headers["Idempotent-Replayed"] == "true"
    assert count_decks(session_factory) == 1


@pytest.mark.parametrize("repeated", ["Fuego", "fuego", " FUÉGO "])
def test_repeated_name_is_a_conflict(api, auth, codes, repeated) -> None:
    assert post(api, auth, "Fuego", codes[:12]).status_code == 201
    response = post(api, auth, repeated, codes[1:13], key="op-2")
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert response.json()["field"] == "name"


def test_two_players_can_use_the_same_name(api, auth, codes) -> None:
    assert post(api, auth, "Fuego", codes[:12]).status_code == 201
    assert post(api, auth, "Fuego", codes[:12], player=RIVAL).status_code == 201


def test_cannot_read_a_deck_of_another_player(api, auth, codes) -> None:
    deck = post(api, auth, "Mío", codes[:12]).json()
    foreign = api.get(f"/v1/mazos/{deck['id']}", headers=auth(RIVAL))
    missing = api.get("/v1/mazos/no-existe", headers=auth(RIVAL))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["message"] == missing.json()["message"]
    assert api.get("/v1/mazos", headers=auth(RIVAL)).json() == {"items": []}


def test_simultaneous_same_name_saves_only_one(codes, session_factory) -> None:
    repository = SqlDeckRepository(session_factory)
    with session_factory() as session:
        card_ids = list(session.scalars(select(CardRow.id).limit(12)))
    barrier = Barrier(2)

    def add(_index: int) -> str:
        barrier.wait(timeout=10)
        try:
            repository.add(PLAYER, "Deck", "same-key", card_ids)
            return "saved"
        except DeckNameConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(add, range(2))) == ["conflict", "saved"]
    assert count_decks(session_factory) == 1


def test_initial_collection_allows_a_valid_deck(
    api, auth, session_factory, codes
) -> None:
    """Criterio de Recibir colección inicial: sus 15 cartas permiten armar un deck."""
    newcomer = "user-3"
    with session_factory.begin() as session:
        session.add(PlayerRow(id=newcomer, name="Misty", email="misty@x.test"))
        session.add(InitialCollectionDeliveryRow(player_id=newcomer))
        session.add_all(
            [
                CardRow(
                    code=f"NEW-{i:03}",
                    name=f"Nueva {i}",
                    search_name=f"nueva {i}",
                    cost=1,
                    power=1,
                    card_type_id=1,
                    rarity_id=1,
                    ability_id=1,
                    image_id=f"new-{i}",
                    status="available",
                )
                for i in range(5)
            ]
        )
    delivery = real_initial_collection_service(session_factory).deliver(newcomer)
    assert delivery.status.value == "delivered"
    with session_factory() as session:
        owned = list(
            session.scalars(
                select(CardRow.code)
                .join(PlayerCardRow, PlayerCardRow.card_id == CardRow.id)
                .where(PlayerCardRow.player_id == newcomer)
            )
        )
    assert len(owned) == 15
    response = post(api, auth, "Inicial", owned[:12], player=newcomer)
    assert response.status_code == 201, response.text
    assert len(api.get("/v1/mazos", headers=auth(newcomer)).json()["items"]) == 1
