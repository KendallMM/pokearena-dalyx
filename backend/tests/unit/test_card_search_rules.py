"""Reglas de los criterios de búsqueda de cartas."""

import pytest

from app.business.catalog.search.card_search_rules import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    build_criteria,
    page_settings,
)
from app.business.catalog.search.models import CardCriteria, CardSearchRequest
from app.business.shared.errors import ValidationFailedError


def test_no_criteria_means_the_whole_catalog() -> None:
    assert build_criteria(CardSearchRequest()) == CardCriteria()


def test_criteria_are_cleaned_and_normalized() -> None:
    criteria = build_criteria(
        CardSearchRequest(
            code=" pka-fue-001 ",
            name="  PIKÁCHU ",
            card_type=" FUE ",
            rarity="RARE",
            ability="HAB-000",
        )
    )
    assert criteria.code == "PKA-FUE-001"
    assert criteria.search_name == "pikachu"
    assert (criteria.card_type, criteria.rarity, criteria.ability) == (
        "FUE",
        "RARE",
        "HAB-000",
    )


def test_blank_criteria_are_ignored() -> None:
    criteria = build_criteria(
        CardSearchRequest(code=" ", name="", card_type="  ", ability="")
    )
    assert criteria == CardCriteria()


def test_exact_value_becomes_a_range_of_one() -> None:
    criteria = build_criteria(CardSearchRequest(cost=3, power=-5))
    assert (criteria.cost_min, criteria.cost_max) == (3, 3)
    assert (criteria.power_min, criteria.power_max) == (-5, -5)


def test_ranges_accept_one_or_both_ends() -> None:
    criteria = build_criteria(CardSearchRequest(cost_min=2, power_max=10))
    assert (criteria.cost_min, criteria.cost_max) == (2, None)
    assert (criteria.power_min, criteria.power_max) == (None, 10)
    criteria = build_criteria(CardSearchRequest(cost_min=2, cost_max=2))
    assert (criteria.cost_min, criteria.cost_max) == (2, 2)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"cost": 11}, "cost"),
        ({"cost": -1}, "cost"),
        ({"power": 21}, "power"),
        ({"power": -21}, "power"),
        ({"cost_min": -1}, "cost_min"),
        ({"cost_max": 11}, "cost_max"),
        ({"power_min": -21}, "power_min"),
        ({"power_max": 21}, "power_max"),
        ({"cost_min": 5, "cost_max": 4}, "cost"),
        ({"power_min": 1, "power_max": 0}, "power"),
        ({"cost": 3, "cost_min": 1}, "cost"),
        ({"power": 3, "power_max": 9}, "power"),
        ({"name": "x" * 101}, "name"),
    ],
)
def test_invalid_criteria_name_the_field(overrides, field) -> None:
    with pytest.raises(ValidationFailedError) as error:
        build_criteria(CardSearchRequest(**overrides))
    assert error.value.field == field


def test_the_bounds_of_cost_and_power_are_valid() -> None:
    build_criteria(CardSearchRequest(cost_min=0, cost_max=10))
    build_criteria(CardSearchRequest(power_min=-20, power_max=20))


def test_page_defaults() -> None:
    assert page_settings(CardSearchRequest()) == (DEFAULT_LIMIT, 0)


def test_page_accepts_its_bounds() -> None:
    assert page_settings(CardSearchRequest(limit=1, last_id=0)) == (1, 0)
    assert page_settings(CardSearchRequest(limit=MAX_LIMIT, last_id=7)) == (
        MAX_LIMIT,
        7,
    )


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": -3}, "limit"),
        ({"limit": MAX_LIMIT + 1}, "limit"),
        ({"last_id": -1}, "last_id"),
    ],
)
def test_invalid_page_settings_name_the_field(overrides, field) -> None:
    with pytest.raises(ValidationFailedError) as error:
        page_settings(CardSearchRequest(**overrides))
    assert error.value.field == field
