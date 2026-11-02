"""LocationService: flujo de crear, validación antes de guardar y miniaturas."""

from io import BytesIO

import pytest
from PIL import Image

from app.business.catalog.content.locations.models import (
    CreateLocation,
    ExtraEnergyMode,
    LocationStatus,
)
from app.business.shared.errors import ValidationFailedError
from tests.unit.image_helpers import make_image


def _command(**overrides) -> CreateLocation:
    values = dict(
        name="Volcán",
        description="Un volcán activo",
        card_limit=3,
        extra_energy_mode="fixed",
        extra_energy_amount=1,
        effect_type="type_bonus",
        effect_parameters={"card_type": "FUE", "amount": 2},
        image_data=make_image(800, 600),
    )
    values.update(overrides)
    return CreateLocation(**values)


def test_creates_location_pending_thumbnail(location_service) -> None:
    stored = location_service.create_location(_command())
    assert stored.id == 1
    assert stored.status is LocationStatus.PENDING_THUMBNAIL


def test_creates_location_without_effect(location_service, location_repository):
    location_service.create_location(_command(effect_type=None, effect_parameters=None))
    saved = location_repository.added[0]
    assert saved.effect_type is None
    assert saved.effect_parameters == {}


def test_image_is_saved_before_the_record(location_service, events) -> None:
    location_service.create_location(_command())
    assert events == ["image_saved", "location_added"]


def test_saved_location_has_normalized_data(
    location_service, location_repository
) -> None:
    location_service.create_location(
        _command(
            name="  Volcán  ",
            effect_type="turn_restriction",
            effect_parameters={"turns": [3, 1]},
        )
    )
    saved = location_repository.added[0]
    assert saved.name == "Volcán"
    assert saved.extra_energy_mode is ExtraEnergyMode.FIXED
    assert saved.effect_parameters == {"turns": [1, 3]}
    assert saved.image_id == "img-1"


def test_card_limit_zero_is_allowed(location_service) -> None:
    assert location_service.create_location(_command(card_limit=0))


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": ""}, "name"),
        ({"description": " "}, "description"),
        ({"card_limit": 6}, "card_limit"),
        ({"card_limit": -1}, "card_limit"),
        ({"extra_energy_mode": "weekly"}, "extra_energy_mode"),
        ({"extra_energy_amount": 4}, "extra_energy_amount"),
        (
            {"extra_energy_mode": "per_card", "extra_energy_amount": 3},
            "extra_energy_amount",
        ),
        ({"effect_type": "teleport"}, "effect_type"),
        ({"effect_parameters": {"card_type": "FUE"}}, "effect_parameters.amount"),
        (
            {"effect_parameters": {"card_type": "FUE", "amount": 9}},
            "effect_parameters.amount",
        ),
    ],
)
def test_invalid_data_is_rejected_and_nothing_is_saved(
    location_service, image_store, location_repository, overrides, field
) -> None:
    with pytest.raises(ValidationFailedError) as error:
        location_service.create_location(_command(**overrides))
    assert error.value.field == field
    assert image_store.saved == {}
    assert location_repository.added == []


@pytest.mark.parametrize(
    "image",
    [
        make_image(600, 840),  # proporción de carta, no 4:3
        make_image(799, 599),  # menor al mínimo
        make_image(1600, 1201),  # 4:3 no exacto
        b"no es una imagen",
    ],
)
def test_invalid_image_is_rejected_and_nothing_is_saved(
    location_service, image_store, location_repository, image
) -> None:
    with pytest.raises(ValidationFailedError) as error:
        location_service.create_location(_command(image_data=image))
    assert error.value.field == "image"
    assert image_store.saved == {}
    assert location_repository.added == []


def test_orphan_image_is_deleted_when_the_record_fails(
    location_service, image_store, location_repository
) -> None:
    location_repository.fail_with = RuntimeError("MySQL no responde")
    with pytest.raises(RuntimeError):
        location_service.create_location(_command())
    assert image_store.deleted == ["img-1"]


def test_failing_orphan_cleanup_does_not_hide_the_original_error(
    location_service, image_store, location_repository
) -> None:
    location_repository.fail_with = RuntimeError("MySQL no responde")
    image_store.fail_delete = True
    with pytest.raises(RuntimeError, match="MySQL"):
        location_service.create_location(_command())


def test_thumbnail_is_320_by_240_and_location_becomes_available(
    location_service, image_store, location_repository
) -> None:
    location_service.create_location(_command(image_data=make_image(1600, 1200)))
    run = location_service.process_pending_thumbnails()
    assert (run.processed, run.failed) == (1, 0)
    thumbnail = image_store.thumbnails["img-1"]
    assert Image.open(BytesIO(thumbnail.data)).size == (320, 240)
    assert location_repository.rows[1]["status"] is LocationStatus.AVAILABLE


def test_failed_thumbnail_keeps_the_location_pending_and_retries(
    location_service, image_store, location_repository, clock
) -> None:
    location_service.create_location(_command())
    image_store.fail_read = True
    run = location_service.process_pending_thumbnails()
    row = location_repository.rows[1]
    assert (run.processed, run.failed) == (0, 1)
    assert row["status"] is LocationStatus.PENDING_THUMBNAIL
    assert row["attempts"] == 1
    assert "MongoDB" in row["last_error"]

    image_store.fail_read = False
    assert location_service.process_pending_thumbnails().processed == 0  # aún espera
    clock.advance(61)
    assert location_service.process_pending_thumbnails().processed == 1
    assert row["status"] is LocationStatus.AVAILABLE


def test_unavailable_location_is_never_available_without_thumbnail(
    location_service, image_store, location_repository
) -> None:
    location_service.create_location(_command())
    image_store.fail_thumbnail_save = True
    location_service.process_pending_thumbnails()
    assert location_repository.rows[1]["status"] is LocationStatus.PENDING_THUMBNAIL
