"""Repositorio de cartas sobre MySQL."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.content.cards.card_code import build_card_code
from app.business.catalog.content.cards.models import CardStatus, NewCard, StoredCard
from app.persistence.relational.models import (
    AbilityRow,
    CardRow,
    CardTypeRow,
    RarityRow,
)


class SqlCardRepository:
    """Implementa el puerto CardRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, card: NewCard) -> StoredCard:
        # Todo ocurre en una transacción: si algo falla, el consecutivo no se consume.
        with self._session_factory.begin() as session:
            number = self._next_number(session, card.card_type)
            code = build_card_code(card.card_type, number)
            row = CardRow(
                code=code,
                name=card.name,
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
