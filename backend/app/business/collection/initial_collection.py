"""Entrega inicial idempotente y reintento de solicitudes persistidas."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Clock

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Resultados contemplados por el diagrama de inicio de sesión."""

    DELIVERED = "delivered"
    ALREADY_DELIVERED = "already_delivered"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"


@dataclass(frozen=True)
class DeliveryResult:
    """Estado de la colección; un fallo de entrega no invalida la autenticación."""

    status: DeliveryStatus
    message: str


class InitialCollectionRepository(Protocol):
    """Persiste la entrega y sus efectos en una única transacción."""

    def deliver(
        self,
        player_id: str,
        card_codes: tuple[str, ...],
        cubes: int | None,
        now: datetime,
        retry_seconds: int,
    ) -> DeliveryResult:
        """Entrega una sola vez o conserva la solicitud pendiente."""
        ...

    def pending_player_ids(self, now: datetime, limit: int) -> list[str]:
        """Lee un lote acotado de entregas cuyo reintento ya corresponde."""
        ...


class InitialCollectionService:
    """Coordina la entrega y reutiliza el planificador de tareas existente."""

    name = "initial_collections"

    def __init__(
        self,
        repository: InitialCollectionRepository,
        clock: Clock,
        card_codes: tuple[str, ...],
        cubes: int | None,
        retry_seconds: int = 60,
        batch_size: int = 20,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._card_codes = card_codes
        self._cubes = cubes
        self._retry_seconds = retry_seconds
        self._batch_size = batch_size

    def deliver(self, player_id: str) -> DeliveryResult:
        """Intenta entregar sin perder el pendiente creado con la cuenta."""
        try:
            return self._repository.deliver(
                player_id,
                self._card_codes,
                self._cubes,
                self._clock.now(),
                self._retry_seconds,
            )
        except ServiceUnavailableError:
            logger.warning("Colección inicial pendiente; se reintentará la entrega")
            return DeliveryResult(
                DeliveryStatus.PENDING,
                "Tu colección inicial está pendiente. Reintentaremos automáticamente.",
            )

    def run(self) -> None:
        """Reintenta incluso si el jugador no vuelve a iniciar sesión."""
        for player_id in self._repository.pending_player_ids(
            self._clock.now(), self._batch_size
        ):
            self.deliver(player_id)
