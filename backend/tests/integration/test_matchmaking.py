"""La API usa SQLite para contratos y MySQL real para concurrencia y recuperación."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, func, insert, select, update

from app.business.matchmaking.elo_queue import Search
from app.business.shared.errors import ConflictError
from app.composition import build_container
from app.main import create_app
from app.persistence.cache.repeated_requests import RedisIdempotencyStore
from app.persistence.cache.request_limits import RedisRequestLimiter
from app.persistence.relational.matchmaking_models import (
    match_players,
    match_searches,
    matches,
)
from app.persistence.relational.models import (
    CardRow,
    DeckCardRow,
    DeckRow,
    ExternalIdentityRow,
    PlayerCardRow,
    PlayerRow,
)
from app.persistence.relational.transactions import session_of
from tests.fakes import InMemoryIdempotencyStore
from tests.integration.test_player_mysql import mysql_sessions

URL = "/v1/busquedas"


def seed(sessions):
    batch = uuid4().hex[:8]
    players = [str(uuid4()) for _ in range(3)]
    decks = [[str(uuid4()), str(uuid4())] for _ in players]
    with sessions.begin() as session:
        cards = [
            CardRow(
                code=f"{batch}{i:02}",
                name=f"Carta {i}",
                search_name=f"carta {i}",
                cost=1,
                power=1,
                card_type_id=1,
                rarity_id=1,
                ability_id=1,
                image_id=f"image-{i}",
                status="available",
            )
            for i in range(12)
        ]
        session.add_all(cards)
        session.add_all(
            PlayerRow(id=player, name=player, email=f"{player}@test.example", cubes=8)
            for player in players
        )
        session.flush()
        session.execute(
            insert(ExternalIdentityRow),
            [
                {"player_id": player, "provider": "google", "subject": player}
                for player in players
            ],
        )
        card_ids = [card.id for card in cards]
        for player, deck_ids in zip(players, decks, strict=True):
            session.execute(
                insert(PlayerCardRow),
                [{"player_id": player, "card_id": card} for card in card_ids],
            )
            session.execute(
                insert(DeckRow),
                [
                    {
                        "id": deck,
                        "player_id": player,
                        "name": str(index),
                        "name_key": str(index),
                    }
                    for index, deck in enumerate(deck_ids)
                ],
            )
            session.execute(
                insert(DeckCardRow),
                [
                    {"deck_id": deck, "card_id": card}
                    for deck in deck_ids
                    for card in card_ids
                ],
            )
    return players, decks, card_ids


def container_for(settings, sessions):
    url = sessions.kw["bind"].url.render_as_string(hide_password=False)
    container = build_container(
        settings.model_copy(update={"mysql_url": url, "scheduler_enabled": False})
    )
    return replace(
        container, idempotency_store=InMemoryIdempotencyStore(), search_limiter=None
    )


@pytest.fixture
def flow(settings, session_factory, make_token):
    players, decks, cards = seed(session_factory)
    container = container_for(settings, session_factory)
    api = TestClient(create_app(container))

    def request(deck=None, *, player=players[0], key="key", role="player", body=None):
        headers = {"Authorization": f"Bearer {make_token(role=role, sub=player)}"}
        if key:
            headers["Idempotency-Key"] = key
        return api.post(
            URL, headers=headers, json=body if body is not None else {"deck_id": deck}
        )

    def auth(player=players[0]):
        return {"Authorization": f"Bearer {make_token(role='player', sub=player)}"}

    return api, container.elo_queue, request, auth, players, decks, cards


def error(response, status, field=None):
    assert response.status_code == status, response.text
    details = response.json()
    assert set(details) == {"code", "message", "field", "correlation_id"}
    assert details["correlation_id"]
    if field is not None:
        assert details["field"] == field
    return details["message"]


def test_contract_ownership_validation_order_and_identity(flow, session_factory):
    api, _, post, _, players, decks, cards = flow
    error(api.post(URL, json={}), 401)
    error(api.post(URL, json={}, headers={"Authorization": "Bearer invalid"}), 401)
    error(post(role="content_admin", key=None), 403)
    error(post(key=None), 400, "Idempotency-Key")
    error(post(), 400, "deck_id")
    error(
        post(body={"deck_id": decks[0][0], "player_id": players[1]}), 400, "player_id"
    )
    assert error(post(str(uuid4())), 404) == error(post(decks[1][0]), 404)
    with session_factory.begin() as session:
        session.execute(
            update(PlayerRow).where(PlayerRow.id == players[0]).values(cubes=0)
        )
        session.execute(
            delete(DeckCardRow).where(
                DeckCardRow.deck_id == decks[0][0], DeckCardRow.card_id == cards[0]
            )
        )
    assert "12 cartas" in error(post(decks[0][0]), 400, "deck_id")


@pytest.mark.parametrize("cubes", [0, 7, 8, 9])
def test_balance(flow, session_factory, cubes):
    _, _, post, _, players, decks, _ = flow
    with session_factory.begin() as session:
        session.execute(
            update(PlayerRow).where(PlayerRow.id == players[0]).values(cubes=cubes)
        )
    response = post(decks[0][0])
    if cubes < 8:
        message = error(response, 400, "cubes")
        assert str(cubes) in message and "Compra cubos" in message
    else:
        assert response.status_code == 202, response.text
    with session_factory() as session:
        assert session.get(PlayerRow, players[0]).cubes == cubes


def test_replays_conflicts_cancel_match_and_private_status(flow, session_factory):
    api, queue, post, auth, players, decks, cards = flow
    response = post(decks[0][0])
    assert response.status_code == 202, response.text
    first = response.json()
    for key in ("key", "new-key"):
        replay = post(decks[0][0], key=key)
        assert replay.status_code == 200 and replay.json() == first
    error(post(decks[0][1]), 409, "Idempotency-Key")
    message = error(post(decks[0][1], key="other"), 409, "deck_id")
    assert first["id"] in message and decks[0][0] in message
    error(api.get(f"{URL}/{first['id']}", headers=auth(players[1])), 404)
    cancelled = api.post(f"{URL}/{first['id']}/cancelar", headers=auth())
    assert cancelled.json()["status"] == "cancelled"
    assert post(decks[0][1], key="after-cancel").status_code == 202
    assert post(decks[1][0], player=players[1]).status_code == 202
    # El mazo que llegó a la fila conserva su composición aunque cambie la referencia.
    with session_factory.begin() as session:
        session.execute(
            delete(DeckCardRow).where(
                DeckCardRow.deck_id == decks[0][1], DeckCardRow.card_id == cards[0]
            )
        )
    queue.match_waiting()
    left = api.get(f"{URL}/actual", headers=auth()).json()
    right = api.get(f"{URL}/actual", headers=auth(players[1])).json()
    assert left["status"] == right["status"] == "found"
    assert left["match_id"] == right["match_id"]
    assert left["deck_id"] == decks[0][1]
    with session_factory() as session:
        snapshots = (
            session.execute(
                select(match_players.c.card_ids).where(
                    match_players.c.match_id == left["match_id"]
                )
            )
            .scalars()
            .all()
        )
        assert snapshots == [cards, cards]
    assert left["match_id"] in error(post(decks[0][0], key="after-found"), 409)
    assert (
        api.post(f"{URL}/{left['id']}/cancelar", headers=auth()).json()["status"]
        == "found"
    )


def test_openapi_uses_the_common_validation_contract(flow):
    api, *_ = flow
    schema = api.get("/openapi.json").json()
    operation = schema["paths"][URL]["post"]

    assert "Jugador" in operation["tags"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert operation["parameters"] == [
        {
            "name": "Idempotency-Key",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "minLength": 1, "maxLength": 128},
        }
    ]
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    assert {"$ref": "#/components/schemas/SearchRequest"} in body["anyOf"]
    models = schema["components"]["schemas"]
    assert set(models["SearchRequest"]["properties"]) == {"deck_id"}
    assert set(models["SearchResponse"]["required"]) == {
        "id",
        "deck_id",
        "mode",
        "status",
        "created_at",
        "match_id",
        "error",
    }
    assert set(models["ErrorResponse"]["properties"]) == {
        "code",
        "message",
        "field",
        "correlation_id",
    }

    success = {"200", "202"}
    errors = {"400", "401", "403", "404", "409", "429", "503", "4XX"}
    assert set(operation["responses"]) == success | errors
    for status, response in operation["responses"].items():
        model = "SearchResponse" if status in success else "ErrorResponse"
        assert response["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{model}"
        }


def test_open_conflicts_in_both_directions(flow):
    _, queue, post, _, players, decks, _ = flow
    tournament, _ = queue.enter(players[0], decks[0][0], mode="tournament")
    assert tournament.id in error(post(decks[0][0]), 409)
    queue.cancel(players[0], tournament.id)
    ranked = post(decks[0][0], key="ranked").json()
    with pytest.raises(ConflictError, match=ranked["id"]):
        queue.enter(players[0], decks[0][0], mode="tournament")


def test_request_limit_uses_authenticated_identity(flow):
    api, _, post, _, players, decks, _ = flow

    class Deny:
        def allow(self, key):
            assert key == f"match_search:{players[0]}"
            return False

    api.app.state.search_limiter = Deny()
    error(post(decks[0][0]), 429)


def test_redis_limiter_failure_allows_ingress_and_logs(flow, caplog):
    api, _, post, _, _, decks, _ = flow
    redis = Mock()
    redis.eval.side_effect = RedisConnectionError()
    api.app.state.search_limiter = RedisRequestLimiter(redis, 30, 60)
    with caplog.at_level("WARNING", logger="app.api.gateway.search_access"):
        response = post(decks[0][0])
    assert response.status_code == 202
    assert "Limitador de búsqueda indisponible" in caplog.text


def test_redis_idempotency_read_failure_rejects_before_ingress(flow):
    api, queue, post, _, players, decks, _ = flow
    redis = Mock()
    redis.get.side_effect = RedisConnectionError()
    api.app.state.idempotency_store = RedisIdempotencyStore(redis)
    error(post(decks[0][0]), 503)
    assert queue.current(players[0]) is None


def test_redis_idempotency_write_failure_returns_503_and_replay_reuses_commit(flow):
    api, queue, post, _, players, decks, _ = flow
    store = api.app.state.idempotency_store
    redis = Mock()
    redis.get.return_value = None
    redis.set.side_effect = RedisConnectionError()
    api.app.state.idempotency_store = RedisIdempotencyStore(redis)
    error(post(decks[0][0]), 503)
    existing = queue.current(players[0])
    assert existing is not None
    api.app.state.idempotency_store = store
    replay = post(decks[0][0])
    assert replay.status_code == 200
    assert replay.json()["id"] == existing.id


@pytest.fixture
def mysql_flow(settings, mysql_sessions):
    players, decks, cards = seed(mysql_sessions)
    left = container_for(settings, mysql_sessions).elo_queue
    right = container_for(settings, mysql_sessions).elo_queue
    return mysql_sessions, left, right, players, decks, cards


def race(first, second):
    barrier = Barrier(2)

    def perform(task):
        barrier.wait(10)
        try:
            return task()
        except ConflictError as failure:
            return failure

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(perform, (first, second)))


@pytest.mark.parametrize(
    "variant",
    ["same", "same-key", "different-deck", "same-key-other-deck", "tournament"],
)
def test_mysql_concurrent_entries(mysql_flow, variant):
    sessions, first, second, players, decks, _ = mysql_flow
    other_deck = decks[0][
        1 if variant in ("different-deck", "same-key-other-deck") else 0
    ]
    other_mode = "tournament" if variant == "tournament" else "ranked"
    other_key = "a" if variant in ("same-key", "same-key-other-deck") else "b"
    results = race(
        lambda: first.enter(players[0], decks[0][0], key_hash="a"),
        lambda: second.enter(
            players[0], other_deck, mode=other_mode, key_hash=other_key
        ),
    )
    with sessions() as session:
        rows = session.execute(
            select(match_searches).where(match_searches.c.player_id == players[0])
        ).all()
    assert len(rows) == 1
    if variant in ("same", "same-key"):
        assert results[0][0].id == results[1][0].id == rows[0].id
        assert sorted(result[1] for result in results) == [False, True]
    else:
        (winner,) = [result[0] for result in results if isinstance(result, tuple)]
        assert winner.deck_id == rows[0].deck_id
        assert sum(isinstance(result, ConflictError) for result in results) == 1


@pytest.mark.parametrize("different_deck", [False, True])
def test_mysql_http_ingress_from_two_api_instances(
    mysql_flow, settings, make_token, different_deck
):
    sessions, queue, _, players, decks, _ = mysql_flow
    apps = [TestClient(create_app(container_for(settings, sessions))) for _ in range(2)]
    token = make_token(role="player", sub=players[0])

    def post(index):
        return apps[index].post(
            URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"request-{index}",
            },
            json={"deck_id": decks[0][index if different_deck else 0]},
        )

    responses = race(lambda: post(0), lambda: post(1))
    assert sorted(response.status_code for response in responses) == (
        [202, 409] if different_deck else [200, 202]
    )
    current = queue.current(players[0])
    for response in responses:
        if response.status_code in (200, 202):
            assert response.json()["id"] == current.id
        else:
            assert current.id in error(response, 409)
    with sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(match_searches)
                .where(match_searches.c.player_id == players[0])
            )
            == 1
        )


def start_players(queue, players, decks):
    return [
        queue.enter(player, deck[0])[0]
        for player, deck in zip(players, decks, strict=True)
    ]


@pytest.mark.parametrize("other_rival", [1, 2])
def test_mysql_competing_workers(mysql_flow, other_rival):
    sessions, first, second, players, decks, _ = mysql_flow
    a, b, c = start_players(first, players, decks)
    rival = [a, b, c][other_rival]
    race(lambda: first.match_pair(a, b), lambda: second.match_pair(a, rival))
    persisted = [first.get(search.player_id, search.id) for search in (a, b, c)]
    found = [search.match_id for search in persisted if search.status == "found"]
    assert len(found) == 2 and found[0] == found[1]
    assert any(search.status == "waiting" for search in persisted)
    with sessions() as session:
        rows = session.execute(
            select(match_players).where(match_players.c.player_id.in_(players))
        ).all()
        assert len(rows) == 2 and {row.match_id for row in rows} == set(found)


def test_mysql_cancel_racing_with_match(mysql_flow):
    _, first, second, players, decks, _ = mysql_flow
    a, b, _ = start_players(first, players, decks)
    _, cancelled = race(
        lambda: first.match_pair(a, b), lambda: second.cancel(a.player_id, a.id)
    )
    current = first.get(a.player_id, a.id)
    rival = first.get(b.player_id, b.id)
    assert current == cancelled
    if current.status == "cancelled":
        assert rival.status == "waiting"
    else:
        assert (
            current.status == rival.status == "found"
            and current.match_id == rival.match_id
        )


def test_mysql_opening_races_with_another_match_creation_flow(mysql_flow):
    _, first, second, players, decks, cards = mysql_flow

    def create_directly():
        now = datetime.now(timezone.utc)
        entries = [
            Search(
                str(uuid4()),
                player,
                player_decks[0],
                cards,
                0,
                "ranked",
                "waiting",
                now,
            )
            for player, player_decks in zip(players[:2], decks[:2], strict=True)
        ]
        with second.transactions.begin() as tx:
            return second.matches.create(tx, *entries)

    opened, match = race(lambda: first.enter(players[0], decks[0][0]), create_directly)
    assert isinstance(opened, ConflictError) != isinstance(match, ConflictError)
    assert bool(first.matches.active(players[0])) == isinstance(opened, ConflictError)


def test_mysql_partial_reservation_is_rolled_back(mysql_flow):
    _, first, second, players, decks, _ = mysql_flow
    a, b, _ = start_players(first, players, decks)
    second.cancel(a.player_id, a.id)
    first.match_pair(a, b)
    assert first.get(a.player_id, a.id).status == "cancelled"
    assert first.get(b.player_id, b.id).status == "waiting"
    assert not first.matches.active(b.player_id)


def test_mysql_checks_persisted_match_after_lost_commit_ack(mysql_flow, monkeypatch):
    sessions, first, second, players, decks, _ = mysql_flow
    a, b, _ = start_players(first, players, decks)
    begin = first.transactions.begin

    @contextmanager
    def lost_commit_ack():
        with begin() as tx:
            yield tx
        raise SimulatedFailure()

    monkeypatch.setattr(first.transactions, "begin", lost_commit_ack)
    first.match_pair(a, b)
    second.match_pair(a, b)
    left, right = (second.get(search.player_id, search.id) for search in (a, b))
    assert left.status == right.status == "found"
    assert left.match_id == right.match_id and not left.error and not right.error
    with sessions() as session:
        rows = session.execute(
            select(match_players).where(match_players.c.player_id.in_(players))
        ).all()
        assert len(rows) == 2 and {row.match_id for row in rows} == {left.match_id}


class SimulatedFailure(Exception):
    pass


@pytest.mark.parametrize(
    "point",
    [
        "one_reserved",
        "both_reserved",
        "during_create",
        "after_insert",
        "one_found",
        "before_commit",
    ],
)
def test_mysql_recovers_at_each_transaction_step(mysql_flow, monkeypatch, point):
    sessions, first, second, players, decks, cards = mysql_flow
    a, b, _ = start_players(first, players, decks)
    repo = first.searches
    match_repo = first.matches.repository

    with monkeypatch.context() as patch:
        if point in ("one_reserved", "both_reserved"):
            original = repo.reserve

            def fail_reserve(tx, ids):
                if point == "one_reserved":
                    session_of(tx).execute(
                        update(match_searches)
                        .where(match_searches.c.id == ids[0])
                        .values(status="reserved")
                    )
                else:
                    original(tx, ids)
                raise SimulatedFailure()

            patch.setattr(repo, "reserve", fail_reserve)
        elif point in ("during_create", "after_insert"):
            original = match_repo.add

            def fail_create(tx, match_id, mode, entries):
                if point == "during_create":
                    session_of(tx).execute(
                        insert(matches).values(id=match_id, mode=mode)
                    )
                else:
                    original(tx, match_id, mode, entries)
                raise SimulatedFailure()

            patch.setattr(match_repo, "add", fail_create)
        else:
            original = repo.found

            def fail_found(tx, ids, match_id):
                if point == "one_found":
                    session_of(tx).execute(
                        update(match_searches)
                        .where(match_searches.c.id == ids[0])
                        .values(status="found", match_id=match_id)
                    )
                else:
                    original(tx, ids, match_id)
                raise SimulatedFailure()

            patch.setattr(repo, "found", fail_found)

        with sessions() as session:
            before = session.scalar(select(func.count()).select_from(matches))
        first.match_pair(a, b)
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(matches)) == before
        for initial in (a, b):
            recovered = second.get(initial.player_id, initial.id)
            assert recovered.status == "waiting" and recovered.match_id is None
            assert recovered.deck_id == initial.deck_id and recovered.card_ids == cards
            assert recovered.created_at == initial.created_at
            assert recovered.error

    second.match_pair(a, b)
    second.match_pair(a, b)
    left, right = (second.get(search.player_id, search.id) for search in (a, b))
    assert left.status == right.status == "found"
    assert left.match_id == right.match_id and not left.error and not right.error
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(matches)) == before + 1
