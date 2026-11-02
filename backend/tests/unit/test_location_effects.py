"""Validación de los efectos de ubicación según el catálogo de tipos."""

import pytest

from app.business.catalog.references.reference_service import ReferenceService
from app.business.shared.errors import ValidationFailedError
from tests.fakes import FakeReferenceRepository


def _validate(effect_type, parameters):
    return ReferenceService(FakeReferenceRepository()).validate_location_effect(
        effect_type, parameters
    )


def test_no_effect_is_valid() -> None:
    assert _validate(None, None) == {}
    assert _validate("", {}) == {}


def test_parameters_without_an_effect_are_rejected() -> None:
    with pytest.raises(ValidationFailedError) as error:
        _validate(None, {"amount": 2})
    assert error.value.field == "effect_parameters"


def test_unknown_effect_type_is_rejected() -> None:
    with pytest.raises(ValidationFailedError) as error:
        _validate("teleport", {})
    assert error.value.field == "effect_type"


def test_type_bonus_requires_an_existing_type_and_an_amount() -> None:
    assert _validate("type_bonus", {"card_type": "FUE", "amount": 3}) == {
        "card_type": "FUE",
        "amount": 3,
    }
    for given, field in [
        ({"amount": 3}, "effect_parameters.card_type"),
        ({"card_type": "FUE"}, "effect_parameters.amount"),
        ({"card_type": "XXX", "amount": 3}, "effect_parameters.card_type"),
        ({"card_type": "FUE", "amount": 6}, "effect_parameters.amount"),
        ({"card_type": "FUE", "amount": -6}, "effect_parameters.amount"),
    ]:
        with pytest.raises(ValidationFailedError) as error:
            _validate("type_bonus", given)
        assert error.value.field == field


@pytest.mark.parametrize("amount", [-5, 0, 5])
def test_amount_accepts_its_bounds(amount) -> None:
    assert _validate("type_bonus", {"card_type": "AGU", "amount": amount})


def test_cost_modifier_type_is_optional() -> None:
    assert _validate("cost_modifier", {"amount": -2}) == {"amount": -2}
    assert _validate("cost_modifier", {"amount": 1, "card_type": "AGU"}) == {
        "amount": 1,
        "card_type": "AGU",
    }
    with pytest.raises(ValidationFailedError) as error:
        _validate("cost_modifier", {"amount": 1, "card_type": "XXX"})
    assert error.value.field == "effect_parameters.card_type"


def test_turn_restriction_accepts_a_list_of_turns_and_sorts_it() -> None:
    assert _validate("turn_restriction", {"turns": [3, 1]}) == {"turns": [1, 3]}


@pytest.mark.parametrize("turns", [[], [0], [7], [1, 1], "1,2", [1.5], [True], None])
def test_turn_restriction_rejects_invalid_turns(turns) -> None:
    with pytest.raises(ValidationFailedError) as error:
        _validate("turn_restriction", {"turns": turns})
    assert error.value.field == "effect_parameters.turns"


@pytest.mark.parametrize("amount", ["2", 2.5, True, None])
def test_amount_must_be_an_integer(amount) -> None:
    with pytest.raises(ValidationFailedError) as error:
        _validate("cost_modifier", {"amount": amount})
    assert error.value.field == "effect_parameters.amount"


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ValidationFailedError) as error:
        _validate("cost_modifier", {"amount": 1, "color": "rojo"})
    assert error.value.field == "effect_parameters.color"
