"""Catálogo visto por el jugador: une el catálogo con sus copias, sin base de datos."""

import pytest

from app.business.catalog.content.cards.models import CardStatus
from app.business.catalog.references.models import Ability, CardType, Rarity
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.search.models import CardSummary, CatalogBrowseRequest
from app.business.collection.catalog_browser import CatalogBrowser
from app.business.shared.errors import ValidationFailedError


def summary(card_id: int) -> CardSummary:
    return CardSummary(
        id=card_id,
        code=f"PKA-FUE-{card_id:03}",
        name=f"Carta {card_id}",
        cost=1,
        power=1,
        card_type=CardType("FUE", "Fuego"),
        rarity=Rarity("COMMON", "Común"),
        ability=Ability("HAB-000", "Sin Habilidad", None),
        status=CardStatus.AVAILABLE,
        thumbnail_attempts=0,
    )


class Owned:
    """Colección en memoria que anota cada lectura."""

    def __init__(self, copies: dict[int, int]) -> None:
        self.copies = copies
        self.calls: list[tuple] = []

    def owned_copies(self, player_id: str) -> dict[int, int]:
        self.calls.append(("owned_copies",))
        return self.copies

    def copies_of(self, player_id: str, card_ids: list[int]) -> dict[int, int]:
        self.calls.append(("copies_of", tuple(card_ids)))
        return {i: n for i, n in self.copies.items() if i in card_ids}


def browser_for(
    card_search_service: CardSearchService, card_search_repository, copies
) -> tuple[CatalogBrowser, Owned]:
    card_search_repository.results = [summary(i) for i in (1, 2, 3)]
    owned = Owned(copies)
    return CatalogBrowser(card_search_service, owned), owned


def test_each_card_says_how_many_copies_the_player_has(
    card_search_service, card_search_repository
) -> None:
    browser, _ = browser_for(card_search_service, card_search_repository, {2: 3})
    page = browser.browse("p1", CatalogBrowseRequest())
    assert [(e.card.id, e.owned, e.copies) for e in page.items] == [
        (1, False, 0),
        (2, True, 3),
        (3, False, 0),
    ]


def test_only_the_copies_of_the_page_are_read(
    card_search_service, card_search_repository
) -> None:
    browser, owned = browser_for(card_search_service, card_search_repository, {2: 3})
    browser.browse("p1", CatalogBrowseRequest(limit=2))
    # Sin "solo mis cartas" no se lee toda la colección, solo las copias de la página.
    assert owned.calls == [("copies_of", (1, 2))]


def test_catalog_for_players_only_shows_available_cards(
    card_search_service, card_search_repository
) -> None:
    browser, _ = browser_for(card_search_service, card_search_repository, {})
    browser.browse("p1", CatalogBrowseRequest(card_type="FUE", cost=2))
    criteria = card_search_repository.calls[-1][0]
    assert criteria.only_available is True
    assert criteria.card_ids is None
    assert (criteria.card_type, criteria.cost_min, criteria.cost_max) == ("FUE", 2, 2)


def test_owned_only_restricts_the_query_to_the_player_cards(
    card_search_service, card_search_repository
) -> None:
    browser, owned = browser_for(
        card_search_service, card_search_repository, {2: 1, 3: 2}
    )
    browser.browse("p1", CatalogBrowseRequest(), only_owned=True)
    criteria = card_search_repository.calls[-1][0]
    assert criteria.card_ids == frozenset({2, 3})
    assert owned.calls[0] == ("owned_copies",)


@pytest.mark.parametrize(
    "request_, field",
    [
        (CatalogBrowseRequest(card_type="DRA"), "card_type"),
        (CatalogBrowseRequest(cost=11), "cost"),
        (CatalogBrowseRequest(limit=0), "limit"),
        (CatalogBrowseRequest(last_id=-1), "last_id"),
    ],
)
def test_invalid_filters_never_read_the_collection(
    card_search_service, card_search_repository, request_, field
) -> None:
    browser, owned = browser_for(card_search_service, card_search_repository, {1: 1})
    with pytest.raises(ValidationFailedError) as error:
        browser.browse("p1", request_, only_owned=True)
    assert error.value.field == field
    assert owned.calls == []
    assert card_search_repository.calls == []


def test_filters_are_validated_type_then_cost_then_pagination(
    card_search_service, card_search_repository
) -> None:
    browser, _ = browser_for(card_search_service, card_search_repository, {})
    everything_wrong = CatalogBrowseRequest(card_type="DRA", cost=11, limit=0)
    with pytest.raises(ValidationFailedError) as error:
        browser.browse("p1", everything_wrong)
    assert error.value.field == "card_type"
    with pytest.raises(ValidationFailedError) as error:
        browser.browse("p1", CatalogBrowseRequest(cost=11, limit=0))
    assert error.value.field == "cost"
