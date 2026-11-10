"""Repositorio de colección: cartas que posee cada jugador."""

from app.business.shared.ports import Transaction
from app.persistence.relational.models import PlayerCardRow
from app.persistence.relational.transactions import session_of


class SqlCollectionRepository:
    """Implementa el puerto CollectionRepository de Colección."""

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
