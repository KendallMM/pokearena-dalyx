"""Búsqueda: caso de uso de buscar cartas con paginación por cursor."""

from collections.abc import Iterable
from dataclasses import replace

from app.business.catalog.ports import CardSearchRepository, ImageStore
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.search.card_search_rules import build_criteria, page_settings
from app.business.catalog.search.models import (
    CardCriteria,
    CardPage,
    CardSearchRequest,
    CatalogBrowseRequest,
    CatalogQuery,
)
from app.business.image_processing.models import StoredImage
from app.business.shared.errors import NotFoundError


class CardSearchService:
    """Valida los criterios, consulta una página y calcula el siguiente cursor."""

    def __init__(
        self,
        references: ReferenceService,
        cards: CardSearchRepository,
        image_store: ImageStore,
    ) -> None:
        self._references = references
        self._cards = cards
        self._image_store = image_store

    def search_cards(self, request: CardSearchRequest) -> CardPage:
        """Todos los criterios activos se cumplen a la vez. Sin criterios recorre el
        catálogo completo. Una página sin resultados es una lista vacía, no un error."""
        criteria = build_criteria(request)
        limit, last_id = page_settings(request)
        self._references.validate_optional_selection(
            criteria.card_type, criteria.rarity, criteria.ability
        )
        return self._fetch(criteria, limit, last_id)

    def prepare_catalog_query(self, request: CatalogBrowseRequest) -> CatalogQuery:
        """Valida los filtros del catálogo del jugador, en este orden: tipo (con
        Referencias), costo y paginación. Lanza ValidationFailedError con el campo y
        los valores permitidos."""
        card_type = (request.card_type or "").strip() or None
        self._references.validate_card_type(card_type)
        search = CardSearchRequest(
            card_type=card_type,
            cost=request.cost,
            cost_min=request.cost_min,
            cost_max=request.cost_max,
            limit=request.limit,
            last_id=request.last_id,
        )
        criteria = replace(build_criteria(search), only_available=True)
        limit, last_id = page_settings(search)
        return CatalogQuery(criteria, limit, last_id)

    def browse_catalog(
        self, query: CatalogQuery, card_ids: Iterable[int] | None = None
    ) -> CardPage:
        """Una página de cartas Disponibles que cumplen los filtros ya validados.
        Con card_ids, solo esas cartas (por ejemplo, las que posee un jugador)."""
        criteria = query.criteria
        if card_ids is not None:
            criteria = replace(criteria, card_ids=frozenset(card_ids))
        return self._fetch(criteria, query.limit, query.last_id)

    def _fetch(self, criteria: CardCriteria, limit: int, last_id: int) -> CardPage:
        # Se pide una carta de más: si llega, hay una página siguiente.
        found = self._cards.search(criteria, after_id=last_id, limit=limit + 1)
        items = found[:limit]
        has_more = len(found) > limit
        return CardPage(items=items, next_cursor=items[-1].id if has_more else None)

    def get_card_image(self, code: str, only_available: bool = False) -> StoredImage:
        """Devuelve la versión grande de la imagen de una carta.

        Con only_available, las cartas que aún no están Disponibles no existen.
        """
        image_id = self._cards.find_image_id(code.strip().upper(), only_available)
        if image_id is None:
            raise NotFoundError("La carta no existe.", field="code")
        try:
            return self._image_store.read_original(image_id)
        except LookupError:
            raise NotFoundError(
                "La imagen de la carta no existe.", field="code"
            ) from None
