"""Repositorio de colección: cartas que posee cada jugador."""

from contextlib import nullcontext

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Transaction
from app.persistence.relational.models import PlayerCardRow
from app.persistence.relational.transactions import session_of

# La colección inicial entrega una copia de cada carta.
ONE_COPY = 1


class SqlCollectionRepository:
    """Implementa los puertos CollectionRepository y OwnedCardsRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def owned_copies(self, player_id: str) -> dict[int, int]:
        """Toda la colección del jugador: copias por identificador de carta."""
        return self._copies(PlayerCardRow.player_id == player_id)

    def copies_of(
        self, player_id: str, card_ids: list[int], *, tx: Transaction | None = None
    ) -> dict[int, int]:
        """Copias de esas cartas que posee el jugador; las que no tiene no aparecen."""
        return self._copies(
            PlayerCardRow.player_id == player_id,
            PlayerCardRow.card_id.in_(card_ids),
            tx=tx,
        )

    def _copies(
        self, *conditions: ColumnElement[bool], tx: Transaction | None = None
    ) -> dict[int, int]:
        try:
            context = nullcontext(session_of(tx)) if tx else self._session_factory()
            with context as session:
                rows = session.execute(
                    select(PlayerCardRow.card_id, PlayerCardRow.quantity).where(
                        *conditions
                    )
                )
                return {card_id: quantity for card_id, quantity in rows}
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo consultar tu colección. Reintenta."
            ) from exc

    def add_cards(
        self, transaction: Transaction, player_id: str, card_ids: list[int]
    ) -> None:
        """Una copia de cada carta. UNIQUE (jugador, carta) impide duplicarlas."""
        session = session_of(transaction)
        session.add_all(
            [
                PlayerCardRow(player_id=player_id, card_id=card_id, quantity=ONE_COPY)
                for card_id in card_ids
            ]
        )
        session.flush()
