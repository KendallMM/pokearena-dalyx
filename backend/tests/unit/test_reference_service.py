"""Servicio de referencias."""

import pytest

from app.business.catalog.references.reference_service import ReferenceService
from app.business.shared.errors import ValidationFailedError
from tests.fakes import FakeReferenceRepository


def test_get_references_groups_all_catalogs() -> None:
    repository = FakeReferenceRepository()
    references = ReferenceService(repository).get_references()
    assert [t.code for t in references.card_types] == ["FUE", "AGU"]
    assert [r.code for r in references.rarities] == ["COMMON", "RARE"]
    assert [a.code for a in references.abilities] == ["HAB-000"]


def _service() -> ReferenceService:
    return ReferenceService(FakeReferenceRepository())


def test_validate_selection_accepts_existing_values() -> None:
    _service().validate_selection("FUE", "COMMON", "HAB-000")


@pytest.mark.parametrize(
    ("selection", "field"),
    [
        (("XXX", "COMMON", "HAB-000"), "card_type"),
        (("FUE", "MYTHIC", "HAB-000"), "rarity"),
        (("FUE", "COMMON", "HAB-999"), "ability"),
        (("FUE", "COMMON", None), "ability"),
        (("FUE", "COMMON", ""), "ability"),
    ],
)
def test_validate_selection_names_the_invalid_field(selection, field) -> None:
    with pytest.raises(ValidationFailedError) as error:
        _service().validate_selection(*selection)
    assert error.value.field == field


def test_missing_ability_asks_to_choose_one_even_if_sin_habilidad() -> None:
    with pytest.raises(ValidationFailedError) as error:
        _service().validate_selection("FUE", "COMMON", None)
    assert "Sin Habilidad" in error.value.message
