"""Armado de piezas reales para las pruebas de integración."""

from app.business.catalog.search.card_search_service import CardSearchService
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.relational.card_search_repository import SqlCardSearchRepository


def real_search_service(session_factory, images, references) -> CardSearchService:
    """Búsqueda sobre la base migrada y MongoDB simulado."""
    return CardSearchService(
        references, SqlCardSearchRepository(session_factory), MongoImageStore(images)
    )
