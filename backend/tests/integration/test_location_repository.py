"""SqlLocationRepository contra la base creada por las migraciones."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.business.catalog.content.locations.models import (
    ExtraEnergyMode,
    LocationStatus,
    NewLocation,
)
from app.persistence.relational.location_repository import SqlLocationRepository
from app.persistence.relational.models import LocationRow

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _location(effect_type="type_bonus", parameters=..., **overrides) -> NewLocation:
    values = dict(
        name="Volcán",
        description="Un volcán activo",
        card_limit=3,
        extra_energy_mode=ExtraEnergyMode.FIXED,
        extra_energy_amount=1,
        effect_type=effect_type,
        effect_parameters=(
            {"card_type": "FUE", "amount": 2} if parameters is ... else parameters
        ),
        image_id="abc123",
        status=LocationStatus.PENDING_THUMBNAIL,
    )
    values.update(overrides)
    return NewLocation(**values)


def test_saves_location_pending_with_its_effect(session_factory) -> None:
    stored = SqlLocationRepository(session_factory).add(_location())
    assert stored.id == 1
    assert stored.status is LocationStatus.PENDING_THUMBNAIL
    with session_factory() as session:
        row = session.scalars(select(LocationRow)).one()
        assert row.status == "pending_thumbnail"
        assert row.effect_parameters == {"card_type": "FUE", "amount": 2}
        assert row.effect_type_id is not None
        assert row.created_at is not None


def test_saves_location_without_effect(session_factory) -> None:
    SqlLocationRepository(session_factory).add(
        _location(effect_type=None, parameters={})
    )
    with session_factory() as session:
        row = session.scalars(select(LocationRow)).one()
        assert row.effect_type_id is None
        assert row.effect_parameters == {}


def test_card_limit_zero_is_stored(session_factory) -> None:
    SqlLocationRepository(session_factory).add(_location(card_limit=0))
    with session_factory() as session:
        assert session.scalars(select(LocationRow.card_limit)).one() == 0


def test_claim_reserves_pending_locations_once(session_factory) -> None:
    repository = SqlLocationRepository(session_factory)
    repository.add(_location())
    repository.add(_location(name="Playa"))

    first = repository.claim_pending_thumbnails(NOW, limit=10, lease_seconds=120)
    again = repository.claim_pending_thumbnails(NOW, limit=10, lease_seconds=120)
    assert [p.id for p in first] == [1, 2]
    assert first[0].label == "ubicación 1"
    assert again == []  # ya están reservadas

    later = NOW + timedelta(seconds=121)
    assert len(repository.claim_pending_thumbnails(later, 10, 120)) == 2


def test_claim_respects_the_batch_limit(session_factory) -> None:
    repository = SqlLocationRepository(session_factory)
    for _ in range(3):
        repository.add(_location())
    assert len(repository.claim_pending_thumbnails(NOW, 2, 120)) == 2


def test_mark_available_only_affects_pending_locations(session_factory) -> None:
    repository = SqlLocationRepository(session_factory)
    repository.add(_location())
    repository.mark_available(1)
    repository.mark_available(99)  # no existe: no pasa nada
    with session_factory() as session:
        row = session.scalars(select(LocationRow)).one()
        assert row.status == "available"
        assert row.thumbnail_claimed_until is None


def test_failure_keeps_it_pending_and_delays_the_retry(session_factory) -> None:
    repository = SqlLocationRepository(session_factory)
    repository.add(_location())
    repository.claim_pending_thumbnails(NOW, 10, 120)
    retry_at = NOW + timedelta(seconds=60)
    repository.register_thumbnail_failure(1, "MongoDB no responde", retry_at)

    with session_factory() as session:
        row = session.scalars(select(LocationRow)).one()
        assert (row.status, row.thumbnail_attempts) == ("pending_thumbnail", 1)
        assert row.thumbnail_last_error == "MongoDB no responde"
    assert (
        repository.claim_pending_thumbnails(NOW + timedelta(seconds=30), 10, 120) == []
    )
    assert len(repository.claim_pending_thumbnails(retry_at, 10, 120)) == 1
