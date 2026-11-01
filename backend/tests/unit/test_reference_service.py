"""Servicio de referencias."""

from app.business.catalog.references.reference_service import ReferenceService
from tests.fakes import FakeReferenceRepository


def test_get_references_groups_all_catalogs() -> None:
    repository = FakeReferenceRepository()
    references = ReferenceService(repository).get_references()
    assert [t.code for t in references.card_types] == ["FUE", "AGU"]
    assert [r.code for r in references.rarities] == ["COMMON", "RARE"]
    assert [a.code for a in references.abilities] == ["HAB-000"]
