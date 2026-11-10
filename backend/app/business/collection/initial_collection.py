"""Participante Colección inicial (Colección y Mazos): subflujo del paso 34 del
inicio de sesión.

Se ejecuta en cada inicio de sesión y solo entrega la primera vez: 15 cartas
Comunes distintas elegidas al azar en el servidor y 1,000 cubos. Todo ocurre en
una sola transacción; si algo falta o falla se deshace y la cuenta nunca queda
con una entrega parcial. Ningún dato del cliente influye en las cartas.
"""

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Protocol

from app.business.catalog.content.cards.card_availability import CardAvailability
from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import (
    Clock,
    RandomSource,
    Transaction,
    TransactionManager,
)

logger = logging.getLogger(__name__)

STARTER_CARD_COUNT = 15
STARTER_CUBES = 1_000
STARTER_RARITY_CODE = "COMMON"
# Motivo con el que la entrega queda en el historial de cubos.
STARTER_CUBES_REASON = "initial_collection"


class DeliveryStatus(str, Enum):
    """Resultado que recibe la API del Jugador."""

    DELIVERED = "delivered"
    ALREADY_DELIVERED = "already_delivered"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"


MESSAGES = {
    DeliveryStatus.DELIVERED: "Recibiste tus 15 cartas iniciales y 1,000 cubos.",
    DeliveryStatus.ALREADY_DELIVERED: "Ya recibiste tu colección inicial.",
    DeliveryStatus.UNAVAILABLE: (
        "El juego aún no está disponible: estamos preparando las cartas iniciales. "
        "Recibirás tu colección en un próximo ingreso."
    ),
    DeliveryStatus.PENDING: (
        "Tu colección inicial está pendiente. Se completará en tu próximo ingreso."
    ),
}


@dataclass(frozen=True)
class DeliveryResult:
    """Estado de la colección; un fallo de entrega no invalida la autenticación."""

    status: DeliveryStatus
    message: str

    @classmethod
    def of(cls, status: DeliveryStatus) -> "DeliveryResult":
        """Resultado con el mensaje que ve el jugador para ese estado."""
        return cls(status, MESSAGES[status])


class StarterPack:
    """Reglas de la colección inicial. Solo el servidor decide qué cartas tocan."""

    rarity_code = STARTER_RARITY_CODE
    card_count = STARTER_CARD_COUNT
    cubes = STARTER_CUBES
    cubes_reason = STARTER_CUBES_REASON

    def __init__(self, random: RandomSource) -> None:
        self._random = random

    def choose_cards(self, candidate_ids: Sequence[int]) -> list[int] | None:
        """Elige cartas distintas al azar, o None si el catálogo no alcanza."""
        candidates = sorted(set(candidate_ids))
        if len(candidates) < self.card_count:
            return None
        return self._random.sample(candidates, self.card_count)


class InitialDeliveryRepository(Protocol):
    """Repositorio de jugadores: la marca de entrega pertenece a la cuenta."""

    def claim_initial_delivery(
        self,
        transaction: Transaction,
        player_id: str,
        now: datetime,
        cubes: int,
        only_if_due: bool,
    ) -> bool:
        """Marca la entrega como hecha solo si aún está pendiente.

        Devuelve False si no cambió ninguna fila. Con only_if_due respeta la
        espera del planificador entre reintentos.
        """
        ...

    def postpone_initial_delivery(self, player_id: str, until: datetime) -> None:
        """Registra un intento fallido, fuera de la transacción de la entrega."""
        ...

    def pending_initial_deliveries(self, now: datetime, limit: int) -> list[str]:
        """Jugadores con entrega pendiente cuyo reintento ya corresponde."""
        ...


class CollectionRepository(Protocol):
    """Repositorio de colección: cartas que posee cada jugador."""

    def add_cards(
        self, transaction: Transaction, player_id: str, card_ids: list[int]
    ) -> None:
        """Agrega una copia de cada carta a la colección del jugador."""
        ...


class CubeRepository(Protocol):
    """Repositorio de cubos: saldo e historial de movimientos, siempre juntos."""

    def credit(
        self,
        transaction: Transaction,
        player_id: str,
        amount: int,
        reason: str,
        reference: str,
    ) -> int:
        """Registra el movimiento, actualiza el saldo y devuelve el saldo nuevo."""
        ...


class InitialCollectionService:
    """Coordina la entrega. El planificador existente también la reintenta."""

    name = "initial_collections"

    def __init__(
        self,
        transactions: TransactionManager,
        deliveries: InitialDeliveryRepository,
        cards: CardAvailability,
        collection: CollectionRepository,
        cubes: CubeRepository,
        clock: Clock,
        random: RandomSource,
        retry_seconds: int = 60,
        batch_size: int = 20,
    ) -> None:
        self._transactions = transactions
        self._deliveries = deliveries
        self._cards = cards
        self._collection = collection
        self._cubes = cubes
        self._clock = clock
        self._pack = StarterPack(random)
        self._retry_seconds = retry_seconds
        self._batch_size = batch_size

    def deliver(self, player_id: str) -> DeliveryResult:
        """Paso 1: en cada ingreso se intenta, sin esperar al planificador."""
        return self._deliver(player_id, only_if_due=False)

    def run(self) -> None:
        """Reintenta incluso si el jugador no vuelve a iniciar sesión."""
        for player_id in self._deliveries.pending_initial_deliveries(
            self._clock.now(), self._batch_size
        ):
            self._deliver(player_id, only_if_due=True)

    def _deliver(self, player_id: str, only_if_due: bool) -> DeliveryResult:
        now = self._clock.now()
        try:
            # Región crítica: una sola transacción.
            with self._transactions.begin() as transaction:
                # Pasos 2–5: marcar la entrega como hecha solo si sigue pendiente.
                claimed = self._deliveries.claim_initial_delivery(
                    transaction, player_id, now, self._pack.cubes, only_if_due
                )
                if not claimed:
                    # Pasos 6–10: ya se entregó o un ingreso simultáneo la entregó.
                    transaction.rollback()
                    return DeliveryResult.of(
                        DeliveryStatus.PENDING
                        if only_if_due
                        else DeliveryStatus.ALREADY_DELIVERED
                    )
                # Pasos 11–16: el módulo Cartas da las Comunes disponibles.
                candidates = self._cards.available_ids(
                    transaction, self._pack.rarity_code
                )
                # Pasos 22–23: el servidor elige 15 distintas al azar.
                chosen = self._pack.choose_cards(candidates)
                if chosen is None:
                    # Pasos 17–21: menos de 15 Comunes; la marca queda pendiente.
                    transaction.rollback()
                    status = DeliveryStatus.UNAVAILABLE
                else:
                    # Pasos 24–27: agregar las cartas a la colección.
                    self._collection.add_cards(transaction, player_id, chosen)
                    # Pasos 28–31: +1,000 cubos como primer movimiento.
                    self._cubes.credit(
                        transaction,
                        player_id,
                        self._pack.cubes,
                        self._pack.cubes_reason,
                        player_id,
                    )
                    # Pasos 32–36: al cerrar sin errores se confirma (COMMIT).
                    return DeliveryResult.of(DeliveryStatus.DELIVERED)
        except ServiceUnavailableError:
            # Pasos 37–41: falló un paso; todo se deshizo y la entrega sigue
            # pendiente. El inicio de sesión continúa.
            logger.warning("Colección inicial pendiente; se reintentará la entrega")
            status = DeliveryStatus.PENDING
        self._postpone(player_id, now)
        return DeliveryResult.of(status)

    def _postpone(self, player_id: str, now: datetime) -> None:
        """Fuera de la transacción: el planificador espera antes de reintentar."""
        try:
            self._deliveries.postpone_initial_delivery(
                player_id, now + timedelta(seconds=self._retry_seconds)
            )
        except ServiceUnavailableError:
            logger.warning("No se pudo registrar el intento de colección inicial")
