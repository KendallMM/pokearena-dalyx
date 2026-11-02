"""Reglas de datos de la carta y código PKA-<TIPO>-<NNN>."""

import pytest

from app.business.catalog.content.cards.card_code import build_card_code
from app.business.catalog.content.cards.card_rules import validate_card_data
from app.business.shared.errors import ConflictError, ValidationFailedError


@pytest.mark.parametrize(("cost", "power"), [(0, -20), (10, 20), (5, 0), (1, 1)])
def test_accepts_values_at_the_limits(cost, power) -> None:
    validate_card_data("Charmander", cost, power)


@pytest.mark.parametrize("cost", [-1, 11, 100])
def test_rejects_cost_out_of_range_naming_the_field(cost) -> None:
    with pytest.raises(ValidationFailedError) as error:
        validate_card_data("Charmander", cost, 0)
    assert error.value.field == "cost"


@pytest.mark.parametrize("power", [-21, 21, 999])
def test_rejects_power_out_of_range_naming_the_field(power) -> None:
    with pytest.raises(ValidationFailedError) as error:
        validate_card_data("Charmander", 1, power)
    assert error.value.field == "power"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_rejects_invalid_name(name) -> None:
    with pytest.raises(ValidationFailedError) as error:
        validate_card_data(name, 1, 1)
    assert error.value.field == "name"


@pytest.mark.parametrize(
    ("type_code", "number", "expected"),
    [
        ("FUE", 1, "PKA-FUE-001"),
        ("AGU", 42, "PKA-AGU-042"),
        ("LUC", 999, "PKA-LUC-999"),
    ],
)
def test_card_code_format(type_code, number, expected) -> None:
    assert build_card_code(type_code, number) == expected


@pytest.mark.parametrize("number", [0, 1000])
def test_card_code_rejects_numbers_outside_three_digits(number) -> None:
    with pytest.raises(ConflictError):
        build_card_code("FUE", number)
