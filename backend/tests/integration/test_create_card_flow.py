"""Flujo completo con MySQL (SQLite migrado) y MongoDB simulado."""

import mongomock
from fastapi.testclient import TestClient
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
from app.persistence.relational.models import CardRow
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_search_service
from tests.fakes import InMemoryIdempotencyStore
from tests.integration.test_create_card_endpoint import FORM, _post


def _locations(session_factory, images, references) -> LocationService:
    return LocationService(
        references,
        ImageProcessor(),
        MongoImageStore(images),
        SqlLocationRepository(session_factory),
        SystemClock(),
    )


def test_create_cards_end_to_end(
    settings, validator, make_token, session_factory
) -> None:
    images = mongomock.MongoClient().db["images"]
    references = ReferenceService(SqlReferenceRepository(session_factory))
    service = CardService(
        references,
        ImageProcessor(),
        MongoImageStore(images),
        SqlCardRepository(session_factory),
        SystemClock(),
    )
    app = create_app(
        Container(
            settings,
            validator,
            InMemoryIdempotencyStore(),
            references,
            service,
            _locations(session_factory, images, references),
            real_search_service(session_factory, images, references),
        )
    )
    client = TestClient(app)
    token = make_token()

    first = _post(client, token, key="a")
    second = _post(client, token, key="b")
    water = _post(client, token, form={**FORM, "card_type": "AGU"}, key="c")
    repeated = _post(client, token, key="a")

    assert first.status_code == second.status_code == water.status_code == 202
    assert [first.json()["code"], second.json()["code"], water.json()["code"]] == [
        "PKA-FUE-001",
        "PKA-FUE-002",
        "PKA-AGU-001",
    ]
    assert repeated.json() == first.json()

    with session_factory() as session:
        rows = session.scalars(select(CardRow).order_by(CardRow.id)).all()
        assert [r.code for r in rows] == ["PKA-FUE-001", "PKA-FUE-002", "PKA-AGU-001"]
        assert {r.status for r in rows} == {"pending_thumbnail"}
    assert images.count_documents({}) == 3
    # cada carta apunta a su imagen guardada
    assert {r.image_id for r in rows} == {str(d["_id"]) for d in images.find()}


def test_created_cards_become_available_after_the_thumbnail_task(
    settings, validator, make_token, session_factory
) -> None:
    from io import BytesIO

    from PIL import Image

    images = mongomock.MongoClient().db["images"]
    references = ReferenceService(SqlReferenceRepository(session_factory))
    service = CardService(
        references,
        ImageProcessor(),
        MongoImageStore(images),
        SqlCardRepository(session_factory),
        SystemClock(),
    )
    client = TestClient(
        create_app(
            Container(
                settings,
                validator,
                InMemoryIdempotencyStore(),
                references,
                service,
                _locations(session_factory, images, references),
                real_search_service(session_factory, images, references),
            )
        )
    )
    token = make_token()
    _post(client, token, key="a")
    _post(client, token, key="b")

    with session_factory() as session:
        assert {r.status for r in session.scalars(select(CardRow))} == {
            "pending_thumbnail"
        }

    run = service.process_pending_thumbnails()
    assert (run.processed, run.failed) == (2, 0)

    with session_factory() as session:
        rows = session.scalars(select(CardRow)).all()
        assert {r.status for r in rows} == {"available"}
        assert all(r.thumbnail_claimed_until is None for r in rows)
    for document in images.find():
        assert document["original"]["width"] == 600  # la original no se toca
        with Image.open(BytesIO(bytes(document["thumbnail"]["data"]))) as thumbnail:
            assert thumbnail.size == (200, 280)

    assert service.process_pending_thumbnails().processed == 0
