"""Límite de ingreso a la fila, compartido por todas las instancias."""

from redis import Redis
from redis.exceptions import RedisError

from app.business.shared.errors import ServiceUnavailableError

INCREMENT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisRequestLimiter:
    def __init__(self, client: Redis, limit: int, window_seconds: int) -> None:
        self.client = client
        self.limit = limit
        self.window_seconds = window_seconds

    def allow(self, key: str) -> bool:
        try:
            count = self.client.eval(
                INCREMENT, 1, "ratelimit:" + key, self.window_seconds
            )
        except RedisError as exc:
            raise ServiceUnavailableError(
                "No se pudo verificar el límite de solicitudes. Reintenta."
            ) from exc
        return int(count) <= self.limit
