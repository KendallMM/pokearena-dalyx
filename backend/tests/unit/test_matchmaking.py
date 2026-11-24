from contextlib import contextmanager, nullcontext
from dataclasses import replace
from unittest.mock import Mock, call
from datetime import datetime, timedelta, timezone

import pytest

from app.business.automatic_tasks.matchmaking_job import ExpireSearchesJob
from app.business.collection.decks import DeckService, validate_composition
from app.business.game.matches import BotOpponent, MatchService
from app.business.matchmaking.elo_queue import (
    EloQueue,
    Search,
    compatible_pairs,
    elo_range,
)
from app.business.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("active", "open_search", "allowed"),
    [
        ("match", None, False),
        (None, ("a", "waiting"), False),
        (None, ("other", "reserved"), False),
        (None, ("a", "reserved"), True),
        (None, None, True),
    ],
)
def test_match_service_decides_which_search_allows_creation(
    active, open_search, allowed
):
    repository, players, searches, tx = (Mock() for _ in range(4))
    repository.active.side_effect = lambda player, _: active if player == "a" else None
    searches.open_for_player.side_effect = lambda _, player: (
        open_search if player == "a" else None
    )
    service = MatchService(repository, players, searches, Mock(), Mock(), Mock())
    a, b = search("a", 0), search("b", 0)
    events = Mock()
    events.attach_mock(players.lock_players, "lock")
    events.attach_mock(repository.active, "active")
    events.attach_mock(searches.open_for_player, "open")
    events.attach_mock(repository.add, "add")
    if allowed:
        match_id = service.create(tx, b, a)
        repository.add.assert_called_once_with(tx, match_id, "ranked", (b, a))
        assert [event[0] for event in events.mock_calls] == [
            "lock",
            "active",
            "open",
            "active",
            "open",
            "add",
        ]
    else:
        with pytest.raises(ConflictError):
            service.create(tx, b, a)
        repository.add.assert_not_called()
    players.lock_players.assert_called_once_with(tx, ["a", "b"])


def search(identifier, elo, seconds=0):
    return Search(
        identifier,
        identifier,
        "deck",
        list(range(12)),
        elo,
        "ranked",
        "waiting",
        NOW - timedelta(seconds=seconds),
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, 100),
        (9.99, 100),
        (10, 150),
        (20, 200),
        (30, 250),
        (40, 300),
        (50, 350),
        (60, 400),
        (360, 400),
    ],
)
def test_range(seconds, expected):
    assert elo_range(seconds) == expected


@pytest.mark.parametrize(
    ("difference", "wait_a", "wait_b", "paired"),
    [
        (99, 0, 0, True),
        (100, 0, 0, True),
        (101, 0, 0, False),
        (150, 10, 10, True),
        (150, 20, 9, False),
        (400, 60, 90, True),
        (401, 80, 90, False),
    ],
)
def test_both_players_must_accept_elo_gap(difference, wait_a, wait_b, paired):
    assert (
        bool(
            compatible_pairs(
                [search("a", 0, wait_a), search("b", difference, wait_b)], NOW
            )
        )
        is paired
    )


def test_oldest_first_nearest_then_age_and_same_player_excluded():
    first = search("a", 0, 30)
    duplicate = replace(search("duplicate", 0, 29), player_id=first.player_id)
    far = search("b", 120, 20)
    near_new = search("d", 40, 10)
    near_old = search("c", 40, 15)
    assert compatible_pairs([near_new, duplicate, near_old, far, first], NOW) == [
        (first, near_old),
        (far, near_new),
    ]
    assert not compatible_pairs([first, duplicate], NOW)


@pytest.mark.parametrize(
    "cards", [list(range(11)), list(range(13)), [0] * 12, list(range(1, 13))]
)
def test_invalid_deck_composition(cards):
    with pytest.raises(ValidationFailedError):
        validate_composition(cards, dict.fromkeys(range(12), 1))


def test_valid_deck_composition():
    validate_composition(list(range(12)), dict.fromkeys(range(12), 1))


@pytest.mark.parametrize("reserved", [0, 1])
def test_bot_reservation_precedes_bot_and_match_creation(reserved):
    calls = Mock()
    repo, matches, bot, tx = calls.repo, calls.matches, calls.bot, Mock()
    entry = replace(search("a", 0, 60), last_seen_at=NOW)
    repo.operation.return_value = None
    repo.in_transaction.return_value = entry
    repo.reserve_bot.return_value = reserved
    repo.found_bot.return_value = 1
    matches.create_against_bot.return_value = "match"
    bot.prepare.return_value = BotOpponent(tuple(range(12)))
    clock = Mock()
    clock.now.return_value = NOW

    @contextmanager
    def transaction():
        yield tx
        calls.commit()

    manager = Mock()
    manager.begin.side_effect = transaction
    queue = EloQueue(repo, Mock(), matches, Mock(), Mock(), manager, clock, bot=bot)
    if not reserved:
        with pytest.raises(ConflictError):
            queue.accept_bot("a", entry.id, "key")
        bot.prepare.assert_not_called()
        matches.create_against_bot.assert_not_called()
        calls.commit.assert_not_called()
    else:
        assert queue.accept_bot("a", entry.id, "key") == "match"
        assert [call[0] for call in calls.mock_calls][-6:] == [
            "repo.reserve_bot",
            "bot.prepare",
            "matches.create_against_bot",
            "repo.found_bot",
            "repo.record_operation",
            "commit",
        ]


def test_expiry_job_delegates_each_time_it_is_invoked():
    queue = Mock()
    job = ExpireSearchesJob(queue)
    job.run()
    queue.expire_abandoned.assert_called_once_with()


@pytest.mark.parametrize("updated", [True, False])
def test_cancel_only_diagnoses_when_update_does_not_change_a_row(updated):
    repo, tx, manager = Mock(), Mock(), Mock()
    manager.begin.return_value = nullcontext(tx)
    cancelled = replace(search("a", 0, 1), status="cancelled")
    repo.cancel_waiting.return_value = cancelled if updated else None
    repo.in_transaction.return_value = cancelled
    queue = EloQueue(repo, Mock(), Mock(), Mock(), Mock(), manager, Mock())

    assert queue.leave("a", cancelled.id) is cancelled
    expected = [call.cancel_waiting(tx, "a", cancelled.id)]
    if not updated:
        expected.append(call.in_transaction(tx, "a", cancelled.id))
    assert repo.mock_calls == expected


def test_missing_and_foreign_decks_share_the_same_error():
    repository = Mock()
    repository.get_for.return_value = None
    collection = Mock()
    service = DeckService(repository, Mock(), collection)
    tx = Mock()
    messages = []
    for deck_id in ("missing-deck", "another-player-deck"):
        with pytest.raises(NotFoundError) as failure:
            service.validate_for_play(tx, "player", deck_id)
        messages.append(failure.value.message)
        repository.get_for.assert_called_with(deck_id, "player", tx=tx)
    assert messages[0] == messages[1]
    collection.copies_of.assert_not_called()


@pytest.mark.parametrize(
    ("deck_id", "active", "balance", "failure"),
    [
        (None, None, 8, ValidationFailedError),
        ("missing", "active-match", 0, NotFoundError),
        ("invalid", "active-match", 0, ValidationFailedError),
        ("deck", "active-match", 0, ConflictError),
        ("deck", None, 0, ValidationFailedError),
        ("deck", None, 7, ValidationFailedError),
        ("deck", None, 8, None),
        ("deck", None, 9, None),
    ],
)
def test_entry_validation(deck_id, active, balance, failure):
    searches, decks, matches, players, cubes, transactions, clock = [
        Mock() for _ in range(7)
    ]
    tx = Mock()
    transactions.begin.return_value = nullcontext(tx)
    decks.validate_for_play.return_value = list(range(12))
    if deck_id in ("missing", "invalid"):
        decks.validate_for_play.side_effect = failure("Error de deck")
    matches.active.return_value = active
    players.elo.return_value = 550
    cubes.balance.return_value = balance
    searches.add.side_effect = lambda _, search: search
    clock.now.return_value = NOW
    queue = EloQueue(searches, decks, matches, players, cubes, transactions, clock)
    calls = Mock()
    calls.attach_mock(decks.validate_for_play, "deck")
    calls.attach_mock(matches.active, "active_match")
    calls.attach_mock(cubes.balance, "balance")
    calls.attach_mock(players.elo, "elo")
    expected = (["deck"] if deck_id else []) + ["active_match", "balance", "elo"]
    if failure is not None:
        with pytest.raises(failure):
            queue.enter("player", deck_id)
        searches.add.assert_not_called()
    else:
        enrolled, created = queue.enter("player", deck_id)
        assert created and enrolled.elo == 550 and enrolled.created_at == NOW
    assert [call[0] for call in calls.mock_calls] == expected
