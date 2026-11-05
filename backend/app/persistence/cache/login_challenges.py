"""Desafíos de Google de un solo uso en el Redis existente."""

from redis import Redis
from redis.exceptions import RedisError

from app.business.shared.errors import ServiceUnavailableError


class RedisLoginChallengeStore:
    """GETDEL impide reutilizar un desafío incluso entre varias instancias."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def create(self, nonce: str, ttl_seconds: int) -> None:
        """Guarda el nonce durante el tiempo máximo permitido para Google."""
        try:
            self._client.set(f"login_challenge:{nonce}", "1", ex=ttl_seconds)
        except RedisError as exc:
            raise ServiceUnavailableError(
                "No se pudo iniciar la autenticación. Reintenta."
            ) from exc

    def consume(self, nonce: str) -> bool:
        """Elimina y lee la clave en una sola operación atómica."""
        try:
            return self._client.getdel(f"login_challenge:{nonce}") is not None
        except RedisError as exc:
            raise ServiceUnavailableError(
                "No se pudo verificar el desafío de inicio de sesión."
            ) from exc
