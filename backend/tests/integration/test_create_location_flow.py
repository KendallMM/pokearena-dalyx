"""Flujo completo de ubicaciones con MySQL (SQLite migrado) y MongoDB simulado."""

from io import BytesIO

import mongomock
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

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
from app.persistence.relational.models import LocationRow
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_search_service
from tests.fakes import InMemoryIdempotencyStore
from tests.integration.test_create_location_endpoint import FORM, _post
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
    return TestClient(app), locations, images


def test_location_is_created_then_becomes_available_with_its_thumbnail(
    settings, validator, make_token, session_factory
) -> None:
    client, locations, images = _build(settings, validator, session_factory)
    token = make_token()
    created = _post(client, token, image=make_image(1600, 1200), key="a")
    repeated = _post(client, token, image=make_image(1600, 1200), key="a")
    assert created.status_code == 202
    assert repeated.json() == created.json()

    with session_factory() as session:
        rows = session.scalars(select(LocationRow)).all()
        assert [(r.status, r.name) for r in rows] == [("pending_thumbnail", "Volcán")]

    run = locations.process_pending_thumbnails()
    assert (run.processed, run.failed) == (1, 0)

    with session_factory() as session:
        assert session.scalars(select(LocationRow.status)).one() == "available"
    stored = images.find_one()
    assert stored["kind"] == "location"
    assert (stored["original"]["width"], stored["original"]["height"]) == (1600, 1200)
    thumbnail = Image.open(BytesIO(bytes(stored["thumbnail"]["data"])))
    assert thumbnail.size == (320, 240)


def test_references_include_the_effect_catalog_from_the_database(
    settings, validator, make_token, session_factory
) -> None:
    client, _, _ = _build(settings, validator, session_factory)
    response = client.get(
        "/admin/referencias", headers={"Authorization": f"Bearer {make_token()}"}
    )
    effects = {e["code"]: e for e in response.json()["location_effect_types"]}
    assert set(effects) == {"type_bonus", "cost_modifier", "turn_restriction"}
    assert effects["turn_restriction"]["parameters"][0]["maximum"] == 6


def test_invalid_effect_is_rejected_and_nothing_is_stored(
    settings, validator, make_token, session_factory
) -> None:
    client, _, images = _build(settings, validator, session_factory)
    form = {**FORM, "effect_type": "teleport"}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 400
    assert response.json()["field"] == "effect_type"
    with session_factory() as session:
        assert session.scalars(select(LocationRow)).all() == []
    assert images.count_documents({}) == 0
