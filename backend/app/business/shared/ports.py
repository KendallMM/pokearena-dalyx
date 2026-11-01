"""Puertos compartidos entre módulos. La persistencia los implementa."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class StoredResponse:
    """Respuesta guardada de una operación ya registrada."""

    status_code: int
    body: dict[str, Any]


class IdempotencyStore(Protocol):
    """Caché compartida entre instancias para reconocer solicitudes repetidas."""

    def get(self, key: str) -> StoredResponse | None:
        """Devuelve la respuesta guardada para la operación, si existe."""
        ...

    def save(self, key: str, response: StoredResponse, ttl_seconds: int) -> None:
        """Guarda la respuesta de la operación por un tiempo limitado."""
        ...
