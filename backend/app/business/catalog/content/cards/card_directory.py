"""Participante Cartas: datos de cartas para otros módulos, por código o identificador.

Mazos lo usa para no consultar las tablas del catálogo directamente (RNF-ARQ-03).
"""

from collections.abc import Collection

from app.business.catalog.ports import CardSearchRepository
from app.business.catalog.search.models import CardCriteria, CardSummary


class CardDirectory:
    """Traduce códigos a identificadores y entrega los datos de las cartas."""

    def __init__(self, cards: CardSearchRepository) -> None:
        self._cards = cards

    def ids_by_code(self, codes: Collection[str]) -> dict[str, int]:
        """Identificador de cada código; los que no existen no aparecen."""
        return self._cards.find_ids_by_codes(list(codes)) if codes else {}

    def summaries(self, card_ids: Collection[int]) -> dict[int, CardSummary]:
        """Datos de esas cartas, por identificador."""
        if not card_ids:
            return {}
        found = self._cards.search(
            CardCriteria(card_ids=frozenset(card_ids)),
            after_id=0,
            limit=len(set(card_ids)),
        )
        return {card.id: card for card in found}
