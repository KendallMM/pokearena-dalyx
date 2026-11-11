"""GET /v1/cartas, /v1/cartas/{code}/imagen y /v1/referencias con la base migrada.

Historia Explorar mi catálogo y mi colección.
"""

import mongomock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.collection.catalog_browser import CatalogBrowser
from app.business.image_processing.image_processor import ImageProcessor
from app.business.image_processing.models import ImageInfo
from app.composition import Container
from app.main import create_app
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.collection_repository import SqlCollectionRepository
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.models import (
    CardRow,
    CardTypeRow,
    PlayerCardRow,
    PlayerRow,
    RarityRow,
)
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_search_service
from tests.fakes import InMemoryIdempotencyStore
from tests.unit.image_helpers import make_image

PLAYER_ID = "user-1"  # el sub de make_token


class Catalog:
    """Arma la app real y siembra cartas, imágenes y la colección del jugador."""

    def __init__(self, settings, validator, session_factory) -> None:
        self.session_factory = session_factory
        images = mongomock.MongoClient().db["images"]
        self.store = MongoImageStore(images)
        references = ReferenceService(SqlReferenceRepository(session_factory))
        search = real_search_service(session_factory, images, references)
        app = create_app(
            Container(
                settings,
                validator,
                InMemoryIdempotencyStore(),
                references,
                CardService(
                    references,
                    ImageProcessor(),
                    self.store,
                    SqlCardRepository(session_factory),
                    SystemClock(),
                ),
                LocationService(
                    references,
                    ImageProcessor(),
                    self.store,
                    SqlLocationRepository(session_factory),
                    SystemClock(),
                ),
                search,
                catalog_browser=CatalogBrowser(
                    search, SqlCollectionRepository(session_factory)
                ),
            )
        )
        self.client = TestClient(app)
        with session_factory.begin() as session:
            session.add(PlayerRow(id=PLAYER_ID, name="Ash", email="ash@x.test"))
        self._count = 0

    def card(
        self,
        card_type: str = "FUE",
        cost: int = 1,
        rarity: str = "COMMON",
        status: str = "available",
        copies: int = 0,
    ) -> str:
        """Agrega una carta con imagen y, si copies > 0, la pone en la colección."""
        self._count += 1
        image = make_image(600, 840)
        image_id = self.store.save_original(
            "card", image, ImageInfo("PNG", "image/png", 600, 840, len(image))
        )
        code = f"TST-{self._count:03}"
        with self.session_factory.begin() as session:
            row = CardRow(
                code=code,
                name=f"Carta {self._count}",
                search_name=f"carta {self._count}",
                cost=cost,
                power=2,
                card_type_id=session.scalar(
                    select(CardTypeRow.id).where(CardTypeRow.code == card_type)
                ),
                rarity_id=session.scalar(
                    select(RarityRow.id).where(RarityRow.code == rarity)
                ),
                ability_id=1,
                image_id=image_id,
                status=status,
            )
            session.add(row)
            session.flush()
            if copies:
                session.add(
                    PlayerCardRow(player_id=PLAYER_ID, card_id=row.id, quantity=copies)
                )
        return code

    def get(self, token: str, path: str = "/v1/cartas", **params):
        return self.client.get(
            path, params=params, headers={"Authorization": f"Bearer {token}"}
        )


@pytest.fixture
def catalog(settings, validator, session_factory: sessionmaker[Session]) -> Catalog:
    return Catalog(settings, validator, session_factory)


@pytest.fixture
def player_token(make_token) -> str:
    return make_token(role="player")


def codes(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [card["code"] for card in response.json()["items"]]


def test_requires_a_player_session(catalog: Catalog, make_token) -> None:
    assert catalog.client.get("/v1/cartas").status_code == 401
    forbidden = catalog.get(make_token(role="content_admin"))
    assert forbidden.status_code == 403


def test_card_shows_all_its_data_and_how_many_copies_i_own(
    catalog: Catalog, player_token: str
) -> None:
    owned = catalog.card(card_type="AGU", cost=3, copies=2)
    missing = catalog.card()
    response = catalog.get(player_token)
    assert codes(response) == [owned, missing]
    first, second = response.json()["items"]
    assert first["name"] == "Carta 1"
    assert (first["cost"], first["power"]) == (3, 2)
    assert first["card_type"] == {"code": "AGU", "name": "Agua"}
    assert first["rarity"] == {"code": "COMMON", "name": "Común"}
    assert first["ability"]["code"]
    assert first["image_url"] == f"/v1/cartas/{owned}/imagen"
    assert (first["owned"], first["copies"]) == (True, 2)
    assert (second["owned"], second["copies"]) == (False, 0)


def test_catalog_is_paginated_with_a_cursor(
    catalog: Catalog, player_token: str
) -> None:
    created = [catalog.card() for _ in range(5)]
    first = catalog.get(player_token, limit=2)
    assert codes(first) == created[:2]
    cursor = first.json()["next_cursor"]
    second = catalog.get(player_token, limit=2, last_id=cursor)
    third = catalog.get(player_token, limit=2, last_id=second.json()["next_cursor"])
    assert codes(second) == created[2:4]
    assert codes(third) == created[4:]
    assert third.json()["next_cursor"] is None


def test_type_and_cost_filters_combine(catalog: Catalog, player_token: str) -> None:
    match = catalog.card(card_type="FUE", cost=3)
    catalog.card(card_type="FUE", cost=5)
    catalog.card(card_type="AGU", cost=3)
    in_range = catalog.card(card_type="FUE", cost=4)
    assert codes(catalog.get(player_token, card_type="FUE", cost=3)) == [match]
    assert codes(
        catalog.get(player_token, card_type="FUE", cost_min=3, cost_max=4)
    ) == [match, in_range]


def test_owned_only_shows_just_my_cards_and_combines_with_filters(
    catalog: Catalog, player_token: str
) -> None:
    mine_fire = catalog.card(card_type="FUE", copies=1)
    catalog.card(card_type="FUE")
    mine_water = catalog.card(card_type="AGU", copies=3)
    assert codes(catalog.get(player_token, owned_only="true")) == [
        mine_fire,
        mine_water,
    ]
    assert codes(catalog.get(player_token, owned_only="true", card_type="AGU")) == [
        mine_water
    ]


def test_owned_only_without_collection_is_an_empty_list(
    catalog: Catalog, player_token: str
) -> None:
    catalog.card()
    response = catalog.get(player_token, owned_only="true")
    assert response.json() == {"items": [], "next_cursor": None}


def test_filters_without_results_return_an_empty_list(
    catalog: Catalog, player_token: str
) -> None:
    catalog.card(card_type="FUE", cost=1)
    response = catalog.get(player_token, card_type="AGU", cost=9)
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_cards_still_processing_their_image_do_not_appear_yet(
    catalog: Catalog, player_token: str
) -> None:
    ready = catalog.card()
    pending = catalog.card(status="pending_thumbnail")
    assert codes(catalog.get(player_token)) == [ready]
    assert catalog.get(player_token, f"/v1/cartas/{pending}/imagen").status_code == 404


def test_unknown_type_is_rejected_listing_the_allowed_values(
    catalog: Catalog, player_token: str
) -> None:
    response = catalog.get(player_token, card_type="DRA")
    assert response.status_code == 400
    body = response.json()
    assert body["field"] == "card_type"
    assert "FUE, AGU, PLA, ELE, PSI, LUC" in body["message"]


@pytest.mark.parametrize(
    "params, field",
    [
        ({"cost": 11}, "cost"),
        ({"cost_min": -1}, "cost_min"),
        ({"cost_max": 99}, "cost_max"),
    ],
)
def test_cost_out_of_range_is_rejected_listing_the_range(
    catalog: Catalog, player_token: str, params: dict, field: str
) -> None:
    response = catalog.get(player_token, **params)
    assert response.status_code == 400
    assert response.json()["field"] == field
    assert "entre 0 y 10" in response.json()["message"]


@pytest.mark.parametrize(
    "params, field, text",
    [
        ({"limit": 0}, "limit", "entre 1 y 100"),
        ({"limit": 101}, "limit", "entre 1 y 100"),
        ({"last_id": -5}, "last_id", "negativo"),
        ({"limit": "diez"}, "limit", "número entero"),
        ({"last_id": "abc"}, "last_id", "número entero"),
        ({"cost": "tres"}, "cost", "número entero"),
        ({"owned_only": "quizas"}, "owned_only", "true o false"),
    ],
)
def test_invalid_parameters_are_descriptive_400s_not_server_errors(
    catalog: Catalog, player_token: str, params: dict, field: str, text: str
) -> None:
    response = catalog.get(player_token, **params)
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "validation_failed"
    assert body["field"] == field
    assert text in body["message"]


def test_image_is_the_large_version(catalog: Catalog, player_token: str) -> None:
    code = catalog.card()
    response = catalog.get(player_token, f"/v1/cartas/{code}/imagen")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == make_image(600, 840)


def test_player_can_load_the_filter_values(catalog: Catalog, player_token: str) -> None:
    response = catalog.get(player_token, "/v1/referencias")
    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["card_types"]
    assert [t["code"] for t in body["card_types"]][:2] == ["FUE", "AGU"]
    assert response.headers["etag"]
