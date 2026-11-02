"""CardSearchService: validación antes de consultar, cursor e imagen."""

import pytest

from app.business.catalog.content.cards.models import CardStatus
from app.business.catalog.references.models import Ability, CardType, Rarity
from app.business.catalog.search.models import CardSearchRequest, CardSummary
from app.business.shared.errors import NotFoundError, ValidationFailedError
from app.business.image_processing.models import ImageInfo
from tests.unit.image_helpers import make_image


def _card(card_id: int) -> CardSummary:
    return CardSummary(
        id=card_id,
        code=f"PKA-FUE-{card_id:03d}",
        name=f"Carta {card_id}",
        cost=1,
        power=1,
        card_type=CardType("FUE", "Fuego"),
        rarity=Rarity("COMMON", "Común"),
        ability=Ability("HAB-000", "Sin Habilidad", None),
        status=CardStatus.AVAILABLE,
        thumbnail_attempts=0,
    )


def test_returns_a_page_and_the_cursor_of_the_next_one(
    card_search_service, card_search_repository
) -> None:
    card_search_repository.results = [_card(i) for i in range(1, 6)]
    page = card_search_service.search_cards(CardSearchRequest(limit=2))
    assert [c.id for c in page.items] == [1, 2]
    assert page.next_cursor == 2


def test_asks_for_one_extra_card_to_know_if_there_are_more(
    card_search_service, card_search_repository
) -> None:
    card_search_service.search_cards(CardSearchRequest(limit=2, last_id=7))
    _, after_id, requested = card_search_repository.calls[0]
    assert (after_id, requested) == (7, 3)


def test_last_page_has_no_cursor(card_search_service, card_search_repository) -> None:
    card_search_repository.results = [_card(i) for i in range(1, 4)]
    page = card_search_service.search_cards(CardSearchRequest(limit=3))
    assert [c.id for c in page.items] == [1, 2, 3]
    assert page.next_cursor is None


def test_walking_all_pages_returns_every_card_once(
    card_search_service, card_search_repository
) -> None:
    card_search_repository.results = [_card(i) for i in range(1, 8)]
    seen, cursor = [], 0
    while True:
        page = card_search_service.search_cards(
            CardSearchRequest(limit=3, last_id=cursor)
        )
        seen += [c.id for c in page.items]
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert seen == [1, 2, 3, 4, 5, 6, 7]


def test_no_results_is_an_empty_page_not_an_error(card_search_service) -> None:
    page = card_search_service.search_cards(CardSearchRequest(name="zzz"))
    assert page.items == [] and page.next_cursor is None


def test_passes_the_normalized_criteria_to_the_repository(
    card_search_service, card_search_repository
) -> None:
    card_search_service.search_cards(
        CardSearchRequest(name="Pikáchu", cost=3, card_type="FUE", ability="HAB-000")
    )
    criteria = card_search_repository.calls[0][0]
    assert criteria.search_name == "pikachu"
    assert (criteria.cost_min, criteria.cost_max) == (3, 3)
    assert (criteria.card_type, criteria.ability) == ("FUE", "HAB-000")


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"card_type": "XXX"}, "card_type"),
        ({"rarity": "MYTHIC"}, "rarity"),
        ({"ability": "HAB-404"}, "ability"),
        ({"cost": 11}, "cost"),
        ({"power_min": 5, "power_max": 1}, "power"),
        ({"limit": 0}, "limit"),
    ],
)
def test_invalid_criteria_never_reach_the_repository(
    card_search_service, card_search_repository, overrides, field
) -> None:
    with pytest.raises(ValidationFailedError) as error:
        card_search_service.search_cards(CardSearchRequest(**overrides))
    assert error.value.field == field
    assert card_search_repository.calls == []


def test_returns_the_large_image_of_a_card(
    card_search_service, card_search_repository, image_store
) -> None:
    data = make_image(600, 840)
    image_store.saved["img-9"] = data
    card_search_repository.image_ids["PKA-FUE-001"] = "img-9"
    image = card_search_service.get_card_image(" pka-fue-001 ")
    assert image.data == data


def test_image_of_an_unknown_card_is_not_found(card_search_service) -> None:
    with pytest.raises(NotFoundError):
        card_search_service.get_card_image("PKA-FUE-404")


def test_missing_image_in_the_store_is_not_found(
    card_search_service, card_search_repository
) -> None:
    card_search_repository.image_ids["PKA-FUE-001"] = "no-existe"
    with pytest.raises(NotFoundError):
        card_search_service.get_card_image("PKA-FUE-001")
