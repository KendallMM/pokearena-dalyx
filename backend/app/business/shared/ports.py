"""Puertos compartidos entre módulos. La persistencia los implementa."""

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


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


class Clock(Protocol):
    """Hora del servidor. Se inyecta para poder controlarla en las pruebas."""

    def now(self) -> datetime:
        """Hora actual en UTC, con zona horaria."""
        ...


class RandomSource(Protocol):
    """Azar del servidor. Se inyecta para poder fijarlo en las pruebas."""

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        """Elige k elementos distintos de la población, sin repetir."""
        ...


class Transaction(Protocol):
    """Transacción abierta que comparten varios repositorios.

    La lógica no ve sus detalles; solo la pasa a cada repositorio y decide si
    se confirma o se deshace.
    """

    def rollback(self) -> None:
        """Pide deshacer todo al cerrar, en lugar de confirmar."""
        ...


class TransactionManager(Protocol):
    """Abre transacciones. Al cerrar confirma, salvo que se pida deshacer o
    falle un paso: entonces deshace todo."""

    def begin(self) -> AbstractContextManager[Transaction]:
        """Abre una transacción; un fallo de la base se informa como
        ServiceUnavailableError."""
        ...
