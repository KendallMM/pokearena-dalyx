"""GET /admin/cartas y GET /admin/cartas/{code}/imagen con la base migrada."""

from io import BytesIO

import mongomock
from fastapi.testclient import TestClient
from PIL import Image

from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.references.reference_service import ReferenceService
from app.business.image_processing.image_processor import ImageProcessor
from app.composition import Container
from app.main import create_app
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_search_service
from tests.fakes import InMemoryIdempotencyStore
from tests.integration.test_create_card_endpoint import FORM, _post
from tests.unit.image_helpers import make_image


def _build(settings, validator, session_factory):
    images = mongomock.MongoClient().db["images"]
    store = MongoImageStore(images)
    references = ReferenceService(SqlReferenceRepository(session_factory))
    cards = CardService(
        references,
        ImageProcessor(),
        store,
        SqlCardRepository(session_factory),
        SystemClock(),
    )
    locations = LocationService(
        references,
        ImageProcessor(),
        store,
        SqlLocationRepository(session_factory),
        SystemClock(),
    )
    app = create_app(
        Container(
            settings,
            validator,
            InMemoryIdempotencyStore(),
            references,
            cards,
            locations,
            real_search_service(session_factory, images, references),
        )
    )
    return TestClient(app), cards


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, key, **changes):
    response = _post(client, token, form={**FORM, **changes}, key=key)
    assert response.status_code == 202, response.text
    return response.json()["code"]


def _search(client, token, **params):
    return client.get("/admin/cartas", params=params, headers=_auth(token))


def test_without_credentials_returns_401(settings, validator, session_factory):
    client, _ = _build(settings, validator, session_factory)
    response = client.get("/admin/cartas")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_without_admin_role_returns_403(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    response = _search(client, make_token(role="player"))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_empty_catalog_returns_an_empty_list(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    response = _search(client, make_token())
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_result_shows_everything_the_admin_reviews(
    settings, validator, make_token, session_factory
):
    client, cards = _build(settings, validator, session_factory)
    token = make_token()
    code = _create(client, token, "a")
    item = _search(client, token).json()["items"][0]
    assert item == {
        "code": code,
        "name": "Charmander",
        "cost": 3,
        "power": 5,
        "card_type": {"code": "FUE", "name": "Fuego"},
        "rarity": {"code": "COMMON", "name": "Común"},
        "ability": {
            "code": "HAB-000",
            "name": "Sin Habilidad",
            "affected_card_type": None,
        },
        "image_url": f"/admin/cartas/{code}/imagen",
        "image_status": "pending_thumbnail",
        "thumbnail_attempts": 0,
    }

    cards.process_pending_thumbnails()
    assert _search(client, token).json()["items"][0]["image_status"] == "available"


def test_criteria_combine_and_ignore_case_and_accents(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    _create(client, token, "a", name="Pikáchu", card_type="ELE", cost="2", power="6")
    _create(client, token, "b", name="Pichu", card_type="ELE", cost="1", power="2")
    _create(client, token, "c", name="Pikachu Gigante", card_type="FUE", cost="9")

    def names(**params):
        return [i["name"] for i in _search(client, token, **params).json()["items"]]

    assert names(name="PIKACHU") == ["Pikáchu", "Pikachu Gigante"]
    assert names(name="pika", card_type="ELE") == ["Pikáchu"]
    assert names(card_type="ELE", cost_min=2) == ["Pikáchu"]
    assert names(cost=1) == ["Pichu"]
    assert names(power_min=3, power_max=7) == ["Pikáchu", "Pikachu Gigante"]
    assert names(power=2) == ["Pichu"]
    assert names(ability="HAB-000", rarity="COMMON", name="gigante") == [
        "Pikachu Gigante"
    ]
    assert names(name="no existe") == []  # sin resultados: lista vacía, no error


def test_search_by_code(settings, validator, make_token, session_factory):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    _create(client, token, "a")
    code = _create(client, token, "b", card_type="AGU")
    items = _search(client, token, code=code.lower()).json()["items"]
    assert [i["code"] for i in items] == [code]


def test_invalid_criteria_return_400_naming_the_criterion(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    cases = [
        ({"card_type": "XXX"}, "card_type"),
        ({"rarity": "MYTHIC"}, "rarity"),
        ({"ability": "HAB-404"}, "ability"),
        ({"cost": 11}, "cost"),
        ({"cost_min": -1}, "cost_min"),
        ({"power": 21}, "power"),
        ({"power_max": 99}, "power_max"),
        ({"cost_min": 5, "cost_max": 4}, "cost"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"last_id": -1}, "last_id"),
        ({"cost": "abc"}, "cost"),
    ]
    for params, field in cases:
        response = _search(client, token, **params)
        assert response.status_code == 400, params
        assert response.json()["field"] == field, params


def test_pagination_is_bounded_and_walks_every_card_once(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    for number in range(5):
        _create(client, token, f"k{number}", name=f"Carta {number}")

    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"last_id": cursor} if cursor else {})}
        body = _search(client, token, **params).json()
        assert len(body["items"]) <= 2
        seen += [i["name"] for i in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"Carta {n}" for n in range(5)]
    assert pages == 3


def test_a_card_created_between_pages_is_neither_repeated_nor_skipped(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    for number in range(3):
        _create(client, token, f"k{number}", name=f"Carta {number}")
    first = _search(client, token, limit=2).json()
    _create(client, token, "nueva", name="Carta 3")
    second = _search(client, token, limit=2, last_id=first["next_cursor"]).json()
    names = [i["name"] for i in first["items"] + second["items"]]
    assert names == [f"Carta {n}" for n in range(4)]
    assert second["next_cursor"] is None


def test_default_page_size_is_bounded(settings, validator, make_token, session_factory):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    for number in range(21):
        _create(client, token, f"k{number}", name=f"Carta {number}")
    body = _search(client, token).json()
    assert len(body["items"]) == 20
    assert body["next_cursor"] is not None


def test_image_endpoint_returns_the_large_version(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    token = make_token()
    code = _create(client, token, "a")
    response = client.get(f"/admin/cartas/{code}/imagen", headers=_auth(token))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(response.content)).size == (600, 840)
    assert response.headers["Cache-Control"] == "private, max-age=3600"


def test_image_endpoint_unknown_card_returns_404(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    response = client.get(
        "/admin/cartas/PKA-FUE-404/imagen", headers=_auth(make_token())
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_image_endpoint_requires_the_admin_role(
    settings, validator, make_token, session_factory
):
    client, _ = _build(settings, validator, session_factory)
    assert client.get("/admin/cartas/PKA-FUE-001/imagen").status_code == 401
    forbidden = client.get(
        "/admin/cartas/PKA-FUE-001/imagen", headers=_auth(make_token(role="player"))
    )
    assert forbidden.status_code == 403
