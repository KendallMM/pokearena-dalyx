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
from app.business.image_processing.models import StoredImage


class OwnedCardsRepository(Protocol):
    """Repositorio de colección: copias que posee cada jugador."""

    def owned_copies(self, player_id: str) -> dict[int, int]:
        """Copias por identificador de carta. Sin cartas, un diccionario vacío."""
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
        copies = self._owned.owned_copies(player_id)
        page = self._catalog.browse_catalog(
            request, card_ids=copies.keys() if only_owned else None
        )
        return CatalogPage(
            items=[CatalogEntry(card, copies.get(card.id, 0)) for card in page.items],
            next_cursor=page.next_cursor,
        )

    def card_image(self, code: str) -> StoredImage:
        """Versión grande de la imagen de una carta Disponible."""
        return self._catalog.get_card_image(code, only_available=True)
