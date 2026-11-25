"""Comprueba la preparación del primer turno con reloj y azar controlados."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.business.game.match_start import MatchPreparationError, MatchStart, draw


def location(identifier, *, limit=2, turns=None, mode="fixed", amount=1):
    return {
        "id": identifier,
        "card_limit": limit,
        "effect_type": "turn_restriction" if turns else None,
        "effect_parameters": {"turns": turns},
        "extra_energy_mode": mode,
        "extra_energy_amount": amount,
    }


def test_prepare_reads_catalog_in_order_and_keeps_original_deck():
    calls = Mock()
    calls.decks.cards_for_match.side_effect = lambda tx, player, deck_id, cards: list(
        cards
    )
    calls.cards.match_versions.return_value = [{"id": i} for i in range(12)]
    calls.locations.match_versions.return_value = [
        location(1),
        location(2, mode="per_card"),
        location(3, limit=0),
        location(4, turns=list(range(1, 7))),
    ]
    calls.clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    calls.random.sample.side_effect = lambda population, count: list(population)[:count]
    preparation = MatchStart(
        calls.decks, calls.cards, calls.locations, calls.clock, calls.random
    )
    cards = list(range(12))
    state = preparation.prepare(Mock(), "bot", [("player", "deck", cards)], cards)
    assert [call[0] for call in calls.mock_calls][:4] == [
        "decks.cards_for_match",
        "decks.cards_for_match",
        "cards.match_versions",
        "locations.match_versions",
    ]
    assert [item["id"] for item in state["locations"]] == [1, 2, 3]
    assert state["deadline"] == "2026-01-01T00:00:30+00:00" and state["stake"] is None
    assert cards == list(range(12))
    for participant in state["participants"]:
        assert participant["energy"] == 4
        assert participant["hand"] == cards[:4]
        assert participant["draw_pile"] == cards[4:]
        assert participant["graveyard"] == []


def test_ineligible_locations_fail_before_random_or_clock():
    decks, cards, locations, clock, random = [Mock() for _ in range(5)]
    decks.cards_for_match.return_value = [1]
    cards.match_versions.return_value = [{"id": 1}]
    locations.match_versions.return_value = [
        location(1),
        location(2, limit=0),
        location(3, turns=list(range(1, 7))),
    ]
    with pytest.raises(MatchPreparationError):
        MatchStart(decks, cards, locations, clock, random).prepare(
            Mock(), "ranked", [("p", "d", [1])]
        )
    random.sample.assert_not_called()
    clock.now.assert_not_called()


def test_draw_does_not_consume_card_at_hand_limit():
    hand, deck = list(range(7)), [7]
    draw(hand, deck)
    assert hand == list(range(7)) and deck == [7]
