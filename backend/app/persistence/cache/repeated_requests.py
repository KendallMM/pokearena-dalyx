"""Solicitudes repetidas: guarda en Redis la respuesta de cada operación."""

import json

from redis import Redis
from redis.exceptions import RedisError

from app.business.shared.errors import ServiceUnavailableError

from app.business.shared.ports import StoredResponse

KEY_PREFIX = "idempotency:"


class RedisIdempotencyStore:
    """Implementa el puerto IdempotencyStore sobre la caché compartida."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, key: str) -> StoredResponse | None:
        try:
            raw = self._client.get(KEY_PREFIX + key)
        except RedisError as exc:
            raise ServiceUnavailableError(
                "No se pudo consultar la operación. Reintenta."
            ) from exc
        if raw is None:
            return None
        data = json.loads(raw)
        return StoredResponse(status_code=data["status_code"], body=data["body"])

    def save(self, key: str, response: StoredResponse, ttl_seconds: int) -> None:
        value = json.dumps({"status_code": response.status_code, "body": response.body})
        try:
            self._client.set(KEY_PREFIX + key, value, ex=ttl_seconds)
        except RedisError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar la respuesta de la operación."
            ) from exc
