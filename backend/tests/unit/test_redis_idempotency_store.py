"""El adaptador de Redis cumple el puerto IdempotencyStore."""

import fakeredis

from app.business.shared.ports import StoredResponse
from app.persistence.cache.repeated_requests import RedisIdempotencyStore


def test_save_and_get_round_trip() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(client)
    response = StoredResponse(202, {"id": 7, "message": "Carta en proceso"})
    store.save("k1", response, ttl_seconds=60)
    assert store.get("k1") == response


def test_unknown_key_returns_none() -> None:
    store = RedisIdempotencyStore(fakeredis.FakeRedis(decode_responses=True))
    assert store.get("nope") is None


def test_response_expires_with_ttl() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(client)
    store.save("k1", StoredResponse(202, {}), ttl_seconds=60)
    assert 0 < client.ttl("idempotency:k1") <= 60
