"""Repositorio de referencias contra la base creada por las migraciones."""

from app.persistence.relational.reference_repository import SqlReferenceRepository


def test_card_types_match_the_story(session_factory) -> None:
    types = SqlReferenceRepository(session_factory).list_card_types()
    assert [(t.code, t.name) for t in types] == [
        ("FUE", "Fuego"),
        ("AGU", "Agua"),
        ("PLA", "Planta"),
        ("ELE", "Eléctrico"),
        ("PSI", "Psíquico"),
        ("LUC", "Lucha"),
    ]


def test_rarities_are_ordered_from_common_to_legendary(session_factory) -> None:
    rarities = SqlReferenceRepository(session_factory).list_rarities()
    assert [r.name for r in rarities] == ["Común", "Poco común", "Rara", "Legendaria"]


def test_no_ability_exists_from_the_start(session_factory) -> None:
    abilities = SqlReferenceRepository(session_factory).list_abilities()
    assert [(a.code, a.name, a.affected_card_type) for a in abilities] == [
        ("HAB-000", "Sin Habilidad", None)
    ]
