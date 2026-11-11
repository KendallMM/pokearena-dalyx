"""Repositorio de colección: cartas que posee cada jugador."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Transaction
from app.persistence.relational.models import PlayerCardRow
from app.persistence.relational.transactions import session_of


class SqlCollectionRepository:
    """Implementa los puertos CollectionRepository y OwnedCardsRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def owned_copies(self, player_id: str) -> dict[int, int]:
        """Copias que posee el jugador, por identificador de carta."""
        try:
            with self._session_factory() as session:
                rows = session.execute(
                    select(PlayerCardRow.card_id, PlayerCardRow.quantity).where(
                        PlayerCardRow.player_id == player_id
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
                PlayerCardRow(player_id=player_id, card_id=card_id, quantity=1)
                for card_id in card_ids
            ]
        )
        session.flush()
