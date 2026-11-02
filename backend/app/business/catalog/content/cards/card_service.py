"""Cartas: caso de uso de crear una carta, en el orden de la secuencia."""

import logging

from app.business.catalog.content.cards.card_image_spec import CARD_IMAGE_SPEC
from app.business.catalog.content.cards.card_rules import validate_card_data
from app.business.catalog.content.cards.models import (
    CardStatus,
    CreateCard,
    NewCard,
    StoredCard,
)
from app.business.catalog.ports import CardRepository, ImageStore
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.thumbnails import (
    ThumbnailGenerator,
    ThumbnailPolicy,
    ThumbnailRun,
)
from app.business.image_processing.image_processor import ImageProcessor
from app.business.shared.ports import Clock

logger = logging.getLogger(__name__)


class CardService:
    """Coordina las reglas de carta, referencias, imagen y guardado."""

    def __init__(
        self,
        references: ReferenceService,
        image_processor: ImageProcessor,
        image_store: ImageStore,
        cards: CardRepository,
        clock: Clock,
        thumbnail_policy: ThumbnailPolicy = ThumbnailPolicy(),
    ) -> None:
        self._references = references
        self._image_processor = image_processor
        self._image_store = image_store
        self._cards = cards
        self._thumbnails = ThumbnailGenerator(
            tracking=cards,
            image_processor=image_processor,
            image_store=image_store,
            clock=clock,
            spec=CARD_IMAGE_SPEC,
            policy=thumbnail_policy,
        )

    def create_card(self, command: CreateCard) -> StoredCard:
        """Valida todo antes de guardar nada. La carta queda pendiente de miniatura."""
        validate_card_data(command.name, command.cost, command.power)
        self._references.validate_selection(
            command.card_type, command.rarity, command.ability
        )
        image_info = self._image_processor.validate(command.image_data, CARD_IMAGE_SPEC)

        # Primero la imagen, luego el registro (ver ADR-002).
        image_id = self._image_store.save_original(
            "card", command.image_data, image_info
        )
        assert command.ability is not None  # ya validada por Referencias
        try:
            return self._cards.add(
                NewCard(
                    name=command.name.strip(),
                    cost=command.cost,
                    power=command.power,
                    card_type=command.card_type,
                    rarity=command.rarity,
                    ability=command.ability,
                    image_id=image_id,
                    status=CardStatus.PENDING_THUMBNAIL,
                )
            )
        except Exception:
            self._discard_image(image_id)
            raise

    def _discard_image(self, image_id: str) -> None:
        """Si no se pudo guardar la carta, intenta no dejar la imagen huérfana."""
        try:
            self._image_store.delete(image_id)
        except Exception:
            logger.error(
                "No se pudo borrar la imagen huérfana %s", image_id, exc_info=True
            )

    def process_pending_thumbnails(self) -> ThumbnailRun:
        """Genera la versión pequeña de las cartas pendientes (ADR-002)."""
        return self._thumbnails.run()
