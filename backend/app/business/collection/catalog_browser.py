"""Historia Explorar mi catálogo y mi colección.

El jugador recorre el catálogo por páginas, filtra por tipo y costo, y ve
cuántas copias posee de cada carta; un filtro muestra solo las suyas. Las
cartas las da el Catálogo; las copias, la Colección. Ninguno lee las tablas del
otro (RNF-ARQ-03).
"""

from dataclasses import dataclass
from typing import Protocol

from app.business.catalog.search.card_search_service import CardSearchService
from app.business.catalog.search.models import CardSummary, CatalogBrowseRequest


class OwnedCardsRepository(Protocol):
    """Repositorio de colección: copias que posee cada jugador."""

    def owned_copies(self, player_id: str) -> dict[int, int]:
        """Toda la colección: copias por identificador de carta."""
        ...

    def copies_of(self, player_id: str, card_ids: list[int]) -> dict[int, int]:
        """Copias de esas cartas que posee el jugador; las que no tiene no aparecen."""
        ...


@dataclass(frozen=True)
class CatalogEntry:
    """Una carta del catálogo y cuántas copias tiene el jugador (0 si no la tiene)."""

    card: CardSummary
    copies: int

    @property
    def owned(self) -> bool:
        return self.copies > 0


@dataclass(frozen=True)
class CatalogPage:
    items: list[CatalogEntry]
    next_cursor: int | None  # None cuando no hay más páginas


class CatalogBrowser:
    """Catálogo visto por un jugador, con su colección."""

    def __init__(self, catalog: CardSearchService, owned: OwnedCardsRepository) -> None:
        self._catalog = catalog
        self._owned = owned

    def browse(
        self, player_id: str, request: CatalogBrowseRequest, only_owned: bool = False
    ) -> CatalogPage:
        """Una página del catálogo. Los filtros activos se cumplen a la vez; sin
        resultados devuelve una lista vacía."""
        # Pasos 27–34: primero se validan los filtros; un error no lee la colección.
        query = self._catalog.prepare_catalog_query(request)
        # Pasos 35–38: solo para "solo mis cartas" se leen las cartas del jugador.
        owned_ids = self._owned.owned_copies(player_id).keys() if only_owned else None
        # Pasos 39–44: Búsqueda devuelve la página y el siguiente cursor.
        page = self._catalog.browse_catalog(query, card_ids=owned_ids)
        # Pasos 45–48: copias de las cartas de esta página.
        ids = [card.id for card in page.items]
        copies = self._owned.copies_of(player_id, ids) if ids else {}
        return CatalogPage(
            items=[CatalogEntry(card, copies.get(card.id, 0)) for card in page.items],
            next_cursor=page.next_cursor,
        )
