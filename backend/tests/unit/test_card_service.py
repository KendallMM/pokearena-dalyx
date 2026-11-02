"""CardService: orden del flujo, validación antes de guardar y limpieza ante fallas."""

import pytest

from app.business.catalog.content.cards.models import CardStatus, CreateCard
from app.business.shared.errors import ValidationFailedError
from tests.unit.image_helpers import make_image


def _command(**overrides) -> CreateCard:
    values = dict(
        name="Charmander",
        cost=3,
        power=5,
        card_type="FUE",
        rarity="COMMON",
        ability="HAB-000",
        image_data=make_image(600, 840),
    )
    values.update(overrides)
    return CreateCard(**values)


def test_creates_card_pending_thumbnail(card_service) -> None:
    stored = card_service.create_card(_command())
    assert stored.code == "PKA-FUE-001"
    assert stored.status is CardStatus.PENDING_THUMBNAIL


def test_image_is_saved_before_the_record(card_service, events) -> None:
    card_service.create_card(_command())
    assert events == ["image_saved", "card_added"]


def test_saved_card_references_the_stored_image(card_service, card_repository) -> None:
    card_service.create_card(_command(name="  Charmander  "))
    card = card_repository.added[0]
    assert card.image_id == "img-1"
    assert card.name == "Charmander"
    assert card.status is CardStatus.PENDING_THUMBNAIL


def test_codes_are_consecutive_per_type(card_service) -> None:
    codes = [
        card_service.create_card(_command(card_type=t)).code
        for t in ["FUE", "FUE", "AGU", "FUE"]
    ]
    assert codes == ["PKA-FUE-001", "PKA-FUE-002", "PKA-AGU-001", "PKA-FUE-003"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": ""}, "name"),
        ({"cost": 11}, "cost"),
        ({"power": -21}, "power"),
        ({"card_type": "XXX"}, "card_type"),
        ({"rarity": "MYTHIC"}, "rarity"),
        ({"ability": None}, "ability"),
        ({"ability": "HAB-404"}, "ability"),
        ({"image_data": make_image(840, 600)}, "image"),
        ({"image_data": make_image(600, 840, "GIF")}, "image"),
        ({"image_data": b"no es imagen"}, "image"),
    ],
)
def test_invalid_data_is_rejected_and_nothing_is_saved(
    card_service, image_store, card_repository, overrides, field
) -> None:
    with pytest.raises(ValidationFailedError) as error:
        card_service.create_card(_command(**overrides))
    assert error.value.field == field
    assert image_store.saved == {}
    assert card_repository.added == []


def test_failure_saving_the_record_removes_the_stored_image(
    card_service, image_store, card_repository
) -> None:
    card_repository.fail_with = RuntimeError("MySQL caído")
    with pytest.raises(RuntimeError, match="MySQL caído"):
        card_service.create_card(_command())
    assert image_store.deleted == ["img-1"]
    assert image_store.saved == {}


def test_failure_removing_the_image_does_not_hide_the_original_error(
    card_service, image_store, card_repository
) -> None:
    card_repository.fail_with = RuntimeError("MySQL caído")
    image_store.fail_delete = True
    with pytest.raises(RuntimeError, match="MySQL caído"):
        card_service.create_card(_command())
