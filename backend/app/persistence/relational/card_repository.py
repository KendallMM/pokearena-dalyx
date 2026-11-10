"""Repositorio de cartas sobre MySQL."""

from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.content.cards.card_code import build_card_code
from app.business.catalog.content.cards.models import (
    CardStatus,
    NewCard,
    PendingCard,
    StoredCard,
)
from app.business.shared.ports import Transaction
from app.persistence.relational.database import naive_utc
from app.persistence.relational.models import (
    AbilityRow,
    CardRow,
    CardTypeRow,
    RarityRow,
)
from app.persistence.relational.transactions import session_of


class SqlCardRepository:
    """Implementa el puerto CardRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def available_ids_by_rarity(
        self, transaction: Transaction, rarity_code: str
    ) -> list[int]:
        """Implementa AvailableCardRepository dentro de la transacción recibida."""
        return list(
            session_of(transaction).scalars(
                select(CardRow.id)
                .join(RarityRow, CardRow.rarity_id == RarityRow.id)
                .where(
                    RarityRow.code == rarity_code,
                    CardRow.status == CardStatus.AVAILABLE.value,
                )
                .order_by(CardRow.id)
            )
        )

    def add(self, card: NewCard) -> StoredCard:
        # Todo ocurre en una transacción: si algo falla, el consecutivo no se consume.
        with self._session_factory.begin() as session:
            number = self._next_number(session, card.card_type)
            code = build_card_code(card.card_type, number)
            row = CardRow(
                code=code,
                name=card.name,
                search_name=card.search_name,
                cost=card.cost,
                power=card.power,
                card_type_id=self._id_of(session, CardTypeRow, card.card_type),
                rarity_id=self._id_of(session, RarityRow, card.rarity),
                ability_id=self._id_of(session, AbilityRow, card.ability),
                image_id=card.image_id,
                status=card.status.value,
            )
            session.add(row)
            session.flush()
            return StoredCard(code=code, status=CardStatus(row.status))

    @staticmethod
    def _next_number(session: Session, type_code: str) -> int:
        """Reserva el siguiente consecutivo del tipo.

        El UPDATE bloquea la fila del tipo hasta que termine la transacción, así dos
        administradores que crean cartas del mismo tipo al mismo tiempo se turnan y
        reciben números distintos.
        """
        session.execute(
            update(CardTypeRow)
            .where(CardTypeRow.code == type_code)
            .values(last_card_number=CardTypeRow.last_card_number + 1)
        )
        return session.scalar(
            select(CardTypeRow.last_card_number).where(CardTypeRow.code == type_code)
        )

    @staticmethod
    def _id_of(
        session: Session, model: type[CardTypeRow | RarityRow | AbilityRow], code: str
    ) -> int:
        return session.scalars(select(model.id).where(model.code == code)).one()

    def claim_pending_thumbnails(
        self, now: datetime, limit: int, lease_seconds: int
    ) -> list[PendingCard]:
        """Reserva cartas pendientes. Cada reserva es un UPDATE condicional: si otra
        instancia ya la tomó, el UPDATE no cambia ninguna fila y se salta esa carta."""
        now_utc = naive_utc(now)
        lease_until = now_utc + timedelta(seconds=lease_seconds)
        free = or_(
            CardRow.thumbnail_claimed_until.is_(None),
            CardRow.thumbnail_claimed_until <= now_utc,
        )
        claimed: list[PendingCard] = []
        with self._session_factory.begin() as session:
            candidates = session.execute(
                select(CardRow.id, CardRow.code, CardRow.image_id)
                .where(CardRow.status == CardStatus.PENDING_THUMBNAIL.value, free)
                .order_by(CardRow.id)
                .limit(limit)
            ).all()
            for card_id, code, image_id in candidates:
                result = session.execute(
                    update(CardRow)
                    .where(
                        CardRow.id == card_id,
                        CardRow.status == CardStatus.PENDING_THUMBNAIL.value,
                        free,
                    )
                    .values(thumbnail_claimed_until=lease_until)
                )
                if result.rowcount == 1:
                    claimed.append(
                        PendingCard(id=card_id, code=code, image_id=image_id)
                    )
        return claimed

    def mark_available(self, card_id: int) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(CardRow)
                .where(
                    CardRow.id == card_id,
                    CardRow.status == CardStatus.PENDING_THUMBNAIL.value,
                )
                .values(
                    status=CardStatus.AVAILABLE.value,
                    thumbnail_claimed_until=None,
                    thumbnail_last_error=None,
                )
            )

    def register_thumbnail_failure(
        self, card_id: int, error: str, retry_at: datetime
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(CardRow)
                .where(CardRow.id == card_id)
                .values(
                    thumbnail_attempts=CardRow.thumbnail_attempts + 1,
                    thumbnail_last_error=error[:500],
                    thumbnail_claimed_until=naive_utc(retry_at),
                )
            )
