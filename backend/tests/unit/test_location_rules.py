"""Reglas de los datos de una ubicación."""

import pytest

from app.business.catalog.content.locations.location_rules import (
    validate_extra_energy,
    validate_location_data,
)
from app.business.catalog.content.locations.models import ExtraEnergyMode
from app.business.shared.errors import ValidationFailedError


def test_accepts_valid_data() -> None:
    validate_location_data("Volcán", "Un volcán activo", 3)


@pytest.mark.parametrize("card_limit", [0, 5])
def test_card_limit_accepts_the_bounds(card_limit) -> None:
    validate_location_data("Volcán", "Un volcán activo", card_limit)


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (("", "desc", 3), "name"),
        (("   ", "desc", 3), "name"),
        (("x" * 101, "desc", 3), "name"),
        (("Volcán", "", 3), "description"),
        (("Volcán", "x" * 501, 3), "description"),
        (("Volcán", "desc", -1), "card_limit"),
        (("Volcán", "desc", 6), "card_limit"),
    ],
)
def test_names_the_invalid_field(args, field) -> None:
    with pytest.raises(ValidationFailedError) as error:
        validate_location_data(*args)
    assert error.value.field == field


@pytest.mark.parametrize(
    ("mode", "amount", "expected"),
    [
        ("fixed", 0, ExtraEnergyMode.FIXED),
        ("fixed", 3, ExtraEnergyMode.FIXED),
        ("per_card", 0, ExtraEnergyMode.PER_CARD),
        ("per_card", 2, ExtraEnergyMode.PER_CARD),
    ],
)
def test_extra_energy_accepts_the_bounds_of_each_mode(mode, amount, expected) -> None:
    assert validate_extra_energy(mode, amount) is expected


@pytest.mark.parametrize(
    ("mode", "amount", "field"),
    [
        ("weekly", 1, "extra_energy_mode"),
        ("", 1, "extra_energy_mode"),
        ("fixed", 4, "extra_energy_amount"),
        ("fixed", -1, "extra_energy_amount"),
        ("per_card", 3, "extra_energy_amount"),
    ],
)
def test_extra_energy_names_the_invalid_field(mode, amount, field) -> None:
    with pytest.raises(ValidationFailedError) as error:
        validate_extra_energy(mode, amount)
    assert error.value.field == field
