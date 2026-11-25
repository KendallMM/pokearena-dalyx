"""MongoDB o MySQL sin respuesta: los adaptadores responden 503 (ServiceUnavailableError).

Cubre el feedback del profesor sobre crear carta y ubicación: si MongoDB falla al
guardar la imagen, la API responde 503 y en MySQL no queda ningún registro.
"""

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError
from sqlalchemy import func, select

from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.cards.models import CardStatus, NewCard
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.content.locations.models import (
    ExtraEnergyMode,
    LocationStatus,
    NewLocation,
)
from app.business.catalog.references.reference_service import ReferenceService
from app.business.image_processing.image_processor import ImageProcessor
from app.business.image_processing.models import ImageInfo, ProcessedImage
from app.business.shared.errors import ServiceUnavailableError
from app.composition import Container
from app.main import create_app
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.database import build_session_factory
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.models import CardRow, LocationRow
from app.persistence.relational.reference_repository import SqlReferenceRepository
from tests.builders import real_search_service
from tests.fakes import InMemoryIdempotencyStore
from tests.integration.test_create_card_endpoint import _post as post_card
from tests.integration.test_create_location_endpoint import _post as post_location

INFO = ImageInfo("PNG", "image/png", 600, 840, 4)
UNREACHABLE_DATABASE = "sqlite:////ruta/que/no/existe/pokearena.db"


class DownCollection:
    """Colección de MongoDB que no responde a ninguna operación."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ServerSelectionTimeoutError("MongoDB no responde")

        return fail


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.save_original("card", b"x", INFO),
        lambda store: store.read_original("0" * 24),
        lambda store: store.save_thumbnail(
            "0" * 24, ProcessedImage(b"x", "image/png", 200, 280)
        ),
        lambda store: store.delete("0" * 24),
    ],
    ids=["save_original", "read_original", "save_thumbnail", "delete"],
)
def test_image_store_translates_mongo_failures_to_503(operation) -> None:
    with pytest.raises(ServiceUnavailableError):
        operation(MongoImageStore(DownCollection()))


def test_card_repository_responds_503_when_mysql_is_down() -> None:
    repository = SqlCardRepository(build_session_factory(UNREACHABLE_DATABASE))
    card = NewCard(
        name="Charmander",
        cost=3,
        power=5,
        card_type="FUE",
        rarity="COMMON",
        ability="HAB-000",
        image_id="abc123",
        status=CardStatus.PENDING_THUMBNAIL,
        search_name="charmander",
    )
    with pytest.raises(ServiceUnavailableError):
        repository.add(card)


def test_location_repository_responds_503_when_mysql_is_down() -> None:
    repository = SqlLocationRepository(build_session_factory(UNREACHABLE_DATABASE))
    location = NewLocation(
        name="Volcán",
        description="Un volcán activo",
        card_limit=3,
        extra_energy_mode=ExtraEnergyMode.FIXED,
        extra_energy_amount=1,
        effect_type=None,
        effect_parameters={},
        image_id="abc123",
        status=LocationStatus.PENDING_THUMBNAIL,
    )
    with pytest.raises(ServiceUnavailableError):
        repository.add(location)


def test_reference_repository_responds_503_when_mysql_is_down() -> None:
    repository = SqlReferenceRepository(build_session_factory(UNREACHABLE_DATABASE))
    with pytest.raises(ServiceUnavailableError):
        repository.list_card_types()


def _client(settings, validator, session_factory, image_collection) -> TestClient:
    images = mongomock.MongoClient().db["images"]
    store = MongoImageStore(image_collection)
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
    return TestClient(app)


def _count(session_factory, row) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(row))


def test_create_card_with_mongo_down_returns_503_and_saves_no_card(
    settings, validator, make_token, session_factory
) -> None:
    client = _client(settings, validator, session_factory, DownCollection())
    response = post_card(client, make_token())
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert _count(session_factory, CardRow) == 0


def test_create_location_with_mongo_down_returns_503_and_saves_no_location(
    settings, validator, make_token, session_factory
) -> None:
    client = _client(settings, validator, session_factory, DownCollection())
    response = post_location(client, make_token())
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert _count(session_factory, LocationRow) == 0
