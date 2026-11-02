"""SqlCardSearchRepository contra la base creada por las migraciones."""

import pytest

from app.business.catalog.content.cards.models import CardStatus, NewCard
from app.business.catalog.search.models import CardCriteria
from app.business.shared.text import normalize_for_search
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.card_search_repository import (
    SqlCardSearchRepository,
    _escape_like,
)
from app.persistence.relational.models import AbilityRow, CardTypeRow


def _add(
    session_factory,
    name,
    card_type="FUE",
    rarity="COMMON",
    cost=3,
    power=5,
    ability="HAB-000",
    status=CardStatus.AVAILABLE,
) -> str:
    return (
        SqlCardRepository(session_factory)
        .add(
            NewCard(
                name=name,
                cost=cost,
                power=power,
                card_type=card_type,
                rarity=rarity,
                ability=ability,
                image_id=f"img-{name}",
                status=status,
                search_name=normalize_for_search(name),
            )
        )
        .code
    )


@pytest.fixture
def repository(session_factory) -> SqlCardSearchRepository:
    return SqlCardSearchRepository(session_factory)


@pytest.fixture
def catalog(session_factory) -> dict[str, str]:
    """Un catálogo pequeño y variado. Devuelve el código de cada carta por nombre."""
    with session_factory.begin() as session:
        water = session.query(CardTypeRow).filter_by(code="AGU").one()
        session.add(
            AbilityRow(code="HAB-001", name="Marea", affected_card_type_id=water.id)
        )
    cards = {
        "Charmander": dict(card_type="FUE", rarity="COMMON", cost=2, power=4),
        "Charizard": dict(card_type="FUE", rarity="LEGENDARY", cost=9, power=18),
        "Squirtle": dict(card_type="AGU", rarity="COMMON", cost=2, power=3),
        "Psíquico Ñandú": dict(
            card_type="PSI", rarity="RARE", cost=5, power=-8, ability="HAB-001"
        ),
        "Cien% Real_": dict(card_type="LUC", rarity="UNCOMMON", cost=0, power=0),
    }
    return {name: _add(session_factory, name, **data) for name, data in cards.items()}


def _names(cards) -> list[str]:
    return [c.name for c in cards]


def _search(repository, after_id=0, limit=50, **criteria):
    return repository.search(CardCriteria(**criteria), after_id, limit)


def test_no_criteria_returns_the_whole_catalog_ordered_by_id(repository, catalog):
    cards = _search(repository)
    assert _names(cards) == list(catalog)
    assert [c.id for c in cards] == sorted(c.id for c in cards)


def test_result_has_everything_the_admin_reviews(repository, catalog):
    card = _search(repository, code=catalog["Psíquico Ñandú"])[0]
    assert (card.code, card.name, card.cost, card.power) == (
        catalog["Psíquico Ñandú"],
        "Psíquico Ñandú",
        5,
        -8,
    )
    assert (card.card_type.code, card.card_type.name) == ("PSI", "Psíquico")
    assert (card.rarity.code, card.rarity.name) == ("RARE", "Rara")
    assert card.ability.code == "HAB-001"
    assert card.ability.affected_card_type == "AGU"  # a qué tipo afecta
    assert card.status is CardStatus.AVAILABLE


def test_ability_without_a_type_limit_affects_all(repository, catalog):
    card = _search(repository, code=catalog["Squirtle"])[0]
    assert card.ability.code == "HAB-000"
    assert card.ability.affected_card_type is None


def test_search_by_code_is_exact(repository, catalog):
    assert _names(_search(repository, code=catalog["Squirtle"])) == ["Squirtle"]
    assert _search(repository, code="PKA-FUE") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("char", ["Charmander", "Charizard"]),  # coincidencia parcial
        ("mander", ["Charmander"]),
        ("squirtle", ["Squirtle"]),
        ("psiquico", ["Psíquico Ñandú"]),  # sin tildes
        ("nandu", ["Psíquico Ñandú"]),
        ("zzz", []),
    ],
)
def test_name_search_is_partial_and_ignores_case_and_accents(
    repository, catalog, text, expected
):
    # El servicio ya entrega el nombre normalizado (sin tildes ni mayúsculas).
    assert _names(_search(repository, search_name=text)) == expected


def test_percent_and_underscore_are_literal_characters(repository, catalog):
    assert _names(_search(repository, search_name="%")) == ["Cien% Real_"]
    assert _names(_search(repository, search_name="_")) == ["Cien% Real_"]
    assert _names(_search(repository, search_name="n_")) == []
    assert _escape_like("a%b_c\\d") == "a\\%b\\_c\\\\d"


def test_cost_exact_and_range(repository, catalog):
    assert _names(_search(repository, cost_min=2, cost_max=2)) == [
        "Charmander",
        "Squirtle",
    ]
    assert _names(_search(repository, cost_min=5)) == ["Charizard", "Psíquico Ñandú"]
    assert _names(_search(repository, cost_max=0)) == ["Cien% Real_"]


def test_power_range_includes_negative_values(repository, catalog):
    assert _names(_search(repository, power_max=0)) == ["Psíquico Ñandú", "Cien% Real_"]
    assert _names(_search(repository, power_min=-10, power_max=3)) == [
        "Squirtle",
        "Psíquico Ñandú",
        "Cien% Real_",
    ]


def test_type_rarity_and_ability(repository, catalog):
    assert _names(_search(repository, card_type="FUE")) == ["Charmander", "Charizard"]
    assert _names(_search(repository, rarity="COMMON")) == ["Charmander", "Squirtle"]
    assert _names(_search(repository, ability="HAB-001")) == ["Psíquico Ñandú"]
    assert len(_search(repository, ability="HAB-000")) == 4  # Sin Habilidad también


def test_criteria_combine_with_and(repository, catalog):
    assert _names(
        _search(repository, card_type="FUE", rarity="COMMON", cost_max=3)
    ) == ["Charmander"]
    assert _names(_search(repository, search_name="char", power_min=10)) == [
        "Charizard"
    ]
    assert _search(repository, card_type="AGU", rarity="LEGENDARY") == []


def test_cards_with_pending_image_are_in_the_complete_catalog(
    repository, session_factory
):
    _add(session_factory, "Nueva", status=CardStatus.PENDING_THUMBNAIL)
    card = _search(repository)[0]
    assert card.status is CardStatus.PENDING_THUMBNAIL
    assert card.thumbnail_attempts == 0


def test_cursor_walks_every_card_once_in_stable_order(repository, session_factory):
    for number in range(1, 8):
        _add(session_factory, f"Carta {number}")
    seen, cursor = [], 0
    while True:
        page = repository.search(CardCriteria(), cursor, 3)
        if not page:
            break
        seen += [c.name for c in page]
        cursor = page[-1].id
    assert seen == [f"Carta {n}" for n in range(1, 8)]


def test_cards_created_while_walking_are_not_repeated_or_skipped(
    repository, session_factory
):
    for number in range(1, 5):
        _add(session_factory, f"Carta {number}")
    first = repository.search(CardCriteria(), 0, 2)
    _add(session_factory, "Carta 5")  # se crea a mitad del recorrido
    second = repository.search(CardCriteria(), first[-1].id, 2)
    third = repository.search(CardCriteria(), second[-1].id, 2)
    names = _names(first) + _names(second) + _names(third)
    assert names == [f"Carta {n}" for n in range(1, 6)]


def test_page_size_is_bounded(repository, session_factory):
    for number in range(1, 6):
        _add(session_factory, f"Carta {number}")
    assert len(repository.search(CardCriteria(), 0, 3)) == 3


def test_find_image_id(repository, catalog):
    assert repository.find_image_id(catalog["Squirtle"]) == "img-Squirtle"
    assert repository.find_image_id("PKA-FUE-404") is None
