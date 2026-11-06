"""Persistencia del participante Colección Inicial, detrás de los mensajes 34–35.

MySQL confirma cartas, cubos y recibo en una sola transacción. El login solo
consume el resultado; estos detalles pertenecen a la User Story de colección.
"""

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.collection.initial_collection import DeliveryResult, DeliveryStatus
from app.business.shared.errors import ServiceUnavailableError
from app.persistence.relational.database import naive_utc
from app.persistence.relational.models import (
    CardRow,
    InitialCollectionDeliveryRow,
    PlayerCardRow,
    PlayerRow,
)


class SqlInitialCollectionRepository:
    """Un UPDATE condicional serializa las entregas de cada jugador en MySQL."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def deliver(
        self,
        player_id: str,
        card_codes: tuple[str, ...],
        cubes: int | None,
        now: datetime,
        retry_seconds: int,
    ) -> DeliveryResult:
        """Un fallo revierte todos los efectos y conserva el pendiente original."""
        now_utc = naive_utc(now)
        try:
            with self._session_factory.begin() as session:
                # El UPDATE toma el bloqueo de esta entrega hasta commit/rollback.
                # Otra solicitud debe esperar y luego comprobar su estado actual.
                claimed = session.execute(
                    update(InitialCollectionDeliveryRow)
                    .where(
                        InitialCollectionDeliveryRow.player_id == player_id,
                        InitialCollectionDeliveryRow.status == "pending",
                        InitialCollectionDeliveryRow.next_attempt_at <= now_utc,
                    )
                    .values(
                        attempts=InitialCollectionDeliveryRow.attempts + 1,
                        next_attempt_at=now_utc + timedelta(seconds=retry_seconds),
                    )
                ).rowcount
                delivery = session.scalars(
                    select(InitialCollectionDeliveryRow).where(
                        InitialCollectionDeliveryRow.player_id == player_id
                    )
                ).one()
                if delivery.status == "delivered":
                    # La recompensa ya está confirmada; este ingreso no suma otra.
                    return DeliveryResult(
                        DeliveryStatus.ALREADY_DELIVERED,
                        "Ya recibiste tu colección inicial.",
                    )
                if not claimed:
                    return DeliveryResult(
                        DeliveryStatus.PENDING,
                        "La colección inicial está pendiente de procesamiento.",
                    )
                return self._grant(session, delivery, card_codes, cubes, now_utc)
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "La colección inicial no está disponible."
            ) from exc

    @staticmethod
    def _grant(
        session: Session,
        delivery: InitialCollectionDeliveryRow,
        card_codes: tuple[str, ...],
        cubes: int | None,
        now: datetime,
    ) -> DeliveryResult:
        """Entrega únicamente cartas reales disponibles, sin fabricar un catálogo."""
        cards = (
            session.scalars(
                select(CardRow.id).where(
                    CardRow.code.in_(card_codes),
                    CardRow.status == "available",
                )
            ).all()
            if card_codes
            else []
        )
        if cubes is None or not card_codes or len(cards) != len(card_codes):
            return DeliveryResult(
                DeliveryStatus.UNAVAILABLE,
                "La colección inicial aún no está disponible. La recibirás automáticamente cuando esté lista.",
            )
        # Las tres escrituras son indivisibles: posesiones, saldo y recibo.
        # Un fallo al confirmar revierte todas y conserva el pendiente original.
        session.add_all(
            [
                PlayerCardRow(player_id=delivery.player_id, card_id=card_id, quantity=1)
                for card_id in cards
            ]
        )
        session.execute(
            update(PlayerRow)
            .where(PlayerRow.id == delivery.player_id)
            .values(cubes=PlayerRow.cubes + cubes)
        )
        delivery.status = "delivered"
        delivery.cubes_granted = cubes
        delivery.delivered_at = now
        return DeliveryResult(
            DeliveryStatus.DELIVERED, "Recibiste tu colección y tus cubos iniciales."
        )

    def pending_player_ids(self, now: datetime, limit: int) -> list[str]:
        """Lee solo pendientes vencidos, usando el índice de estado y fecha."""
        try:
            with self._session_factory() as session:
                return list(
                    session.scalars(
                        select(InitialCollectionDeliveryRow.player_id)
                        .where(
                            InitialCollectionDeliveryRow.status == "pending",
                            InitialCollectionDeliveryRow.next_attempt_at
                            <= naive_utc(now),
                        )
                        .order_by(
                            InitialCollectionDeliveryRow.next_attempt_at,
                            InitialCollectionDeliveryRow.id,
                        )
                        .limit(limit)
                    )
                )
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudieron consultar las entregas pendientes."
            ) from exc
