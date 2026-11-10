"""Participante Cartas: qué cartas del catálogo se pueden entregar a jugadores.

Es la puerta del Catálogo para otros módulos (por ejemplo, Colección), que así
no consultan las tablas del catálogo directamente (RNF-ARQ-03).
"""

from app.business.catalog.ports import AvailableCardRepository
from app.business.shared.ports import Transaction


class CardAvailability:
    """Consulta las cartas Disponibles dentro de la transacción de quien pregunta."""

    def __init__(self, cards: AvailableCardRepository) -> None:
        self._cards = cards

    def available_ids(self, transaction: Transaction, rarity_code: str) -> list[int]:
        """Identificadores de las cartas Disponibles de la rareza indicada."""
        return self._cards.available_ids_by_rarity(transaction, rarity_code)
