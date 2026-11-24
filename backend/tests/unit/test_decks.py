"""Reglas de Crear un deck, sin base de datos."""

import pytest

from app.business.catalog.content.cards.card_directory import CardDirectory
from app.business.collection.decks import (
    DeckNameConflictError,
    DeckService,
    StoredDeck,
    clean_deck_name,
    deck_name_key,
)
from app.business.shared.errors import NotFoundError, ValidationFailedError

CODES = [f"C{i:02}" for i in range(1, 15)]
IDS = {code: index for index, code in enumerate(CODES, 1)}


class World:
    """Dobles de Cartas, Colección y Mazos; anotan las lecturas."""

    def __init__(self, owned: set[int] | None = None) -> None:
        self.owned = set(IDS.values()) if owned is None else owned
        self.calls: list[str] = []
        self.saved: list[tuple] = []

    def find_ids_by_codes(self, codes):
        self.calls.append("cards")
        return {code: IDS[code] for code in codes if code in IDS}

    def search(self, criteria, after_id, limit):
        return []

    def copies_of(self, player_id, card_ids):
        self.calls.append("collection")
        return {i: 1 for i in card_ids if i in self.owned}

    def add(self, player_id, name, name_key, card_ids):
        self.saved.append((player_id, name, name_key, card_ids))
        return StoredDeck("deck-1", name, card_ids)

    def list_for(self, player_id):
        return []

    def get_for(self, deck_id, player_id):
        return None


def service(world: World) -> DeckService:
    return DeckService(world, CardDirectory(world), world)


def rejected(world: World, name: str, codes: list[str]) -> ValidationFailedError:
    with pytest.raises(ValidationFailedError) as error:
        service(world).create("p1", name, codes)
    assert world.saved == []
    return error.value


def test_twelve_distinct_owned_cards_are_saved() -> None:
    world = World()
    created = service(world).create("p1", "  Mi   deck ", CODES[:12])
    assert (created.name, created.card_codes) == ("Mi deck", CODES[:12])
    assert world.calls == ["cards", "collection"]
    assert world.saved[0][3] == list(range(1, 13))


@pytest.mark.parametrize("count", [0, 11, 13])
def test_wrong_count_reports_the_current_amount_without_reading(count: int) -> None:
    world = World()
    error = rejected(world, "Deck", CODES[:count])
    assert (error.field, f"tiene {count}" in error.message) == ("cards", True)
    assert world.calls == []


def test_repeated_cards_are_listed_without_reading() -> None:
    world = World()
    codes = CODES[:10] + ["c01", " C02 "]
    error = rejected(world, "Deck", codes)
    assert "C01, C02" in error.message
    assert world.calls == []


def test_unowned_and_unknown_cards_are_listed() -> None:
    world = World(owned=set(range(2, 13)))
    codes = CODES[:11] + ["NOPE"]
    error = rejected(world, "Deck", codes)
    assert "C01, NOPE" in error.message


def test_checks_run_in_order_name_count_repeated() -> None:
    assert rejected(World(), " ", CODES[:1]).field == "name"
    assert "tiene 2" in rejected(World(), "Deck", ["C01", "C01"]).message


@pytest.mark.parametrize("name", ["", "   ", "́", "x" * 41])
def test_invalid_names_are_rejected(name: str) -> None:
    with pytest.raises(ValidationFailedError) as error:
        clean_deck_name(name)
    assert error.value.field == "name"


def test_name_key_ignores_case_accents_and_spaces() -> None:
    assert deck_name_key("Fuégo  Rojo") == deck_name_key(" fuego rojo ")
    assert deck_name_key("Fuego") != deck_name_key("Agua")


def test_foreign_or_missing_deck_is_not_found() -> None:
    with pytest.raises(NotFoundError):
        service(World()).get_deck("p1", "other")


def test_name_conflict_points_to_the_name() -> None:
    error = DeckNameConflictError("Fuego")
    assert error.field == "name" and "Fuego" in error.message
