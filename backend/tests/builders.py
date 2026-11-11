"""Armado de piezas reales para las pruebas de integración."""

from app.business.catalog.content.cards.card_availability import CardAvailability
from app.business.catalog.search.card_search_service import CardSearchService
from app.business.collection.initial_collection import InitialCollectionService
from app.persistence.documents.image_repository import MongoImageStore
from app.persistence.integrations.system_clock import SystemClock
from app.persistence.integrations.system_random import SystemRandomSource
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.card_search_repository import SqlCardSearchRepository
from app.persistence.relational.collection_repository import SqlCollectionRepository
from app.persistence.relational.cube_repository import SqlCubeRepository
from app.persistence.relational.player_repository import SqlPlayerRepository
from app.persistence.relational.transactions import SqlTransactionManager


def real_search_service(session_factory, images, references) -> CardSearchService:
    """Búsqueda sobre la base migrada y MongoDB simulado."""
    return CardSearchService(
        references, SqlCardSearchRepository(session_factory), MongoImageStore(images)
    )


def real_initial_collection_service(
    session_factory, clock=None, random=None
) -> InitialCollectionService:
    """Colección inicial con los repositorios reales y una transacción compartida."""
    return InitialCollectionService(
        transactions=SqlTransactionManager(session_factory),
        deliveries=SqlPlayerRepository(session_factory),
        cards=CardAvailability(SqlCardRepository(session_factory)),
        collection=SqlCollectionRepository(session_factory),
        cubes=SqlCubeRepository(),
        clock=clock or SystemClock(),
        random=random or SystemRandomSource(),
    )
