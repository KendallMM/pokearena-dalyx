"""Catálogo visto por el jugador: une el catálogo con sus copias, sin base de datos."""

from app.business.catalog.content.cards.models import CardStatus
from app.business.catalog.references.models import Ability, CardType, Rarity
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.search.models import CardSummary, CatalogBrowseRequest
from app.business.collection.catalog_browser import CatalogBrowser


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
    def __init__(self, copies: dict[int, int]) -> None:
        self.copies = copies

    def owned_copies(self, player_id: str) -> dict[int, int]:
        return self.copies


def browser_for(
    card_search_service: CardSearchService, card_search_repository, copies
) -> CatalogBrowser:
    card_search_repository.results = [summary(i) for i in (1, 2, 3)]
    return CatalogBrowser(card_search_service, Owned(copies))


def test_each_card_says_how_many_copies_the_player_has(
    card_search_service, card_search_repository
) -> None:
    browser = browser_for(card_search_service, card_search_repository, {2: 3})
    page = browser.browse("p1", CatalogBrowseRequest())
    assert [(e.card.id, e.owned, e.copies) for e in page.items] == [
        (1, False, 0),
        (2, True, 3),
        (3, False, 0),
    ]


def test_catalog_for_players_only_shows_available_cards(
    card_search_service, card_search_repository
) -> None:
    browser = browser_for(card_search_service, card_search_repository, {})
    browser.browse("p1", CatalogBrowseRequest(card_type="FUE", cost=2))
    criteria = card_search_repository.calls[-1][0]
    assert criteria.only_available is True
    assert criteria.card_ids is None
    assert (criteria.card_type, criteria.cost_min, criteria.cost_max) == ("FUE", 2, 2)


def test_owned_only_restricts_the_query_to_the_player_cards(
    card_search_service, card_search_repository
) -> None:
    browser = browser_for(card_search_service, card_search_repository, {2: 1, 3: 2})
    browser.browse("p1", CatalogBrowseRequest(), only_owned=True)
    criteria = card_search_repository.calls[-1][0]
    assert criteria.card_ids == frozenset({2, 3})
