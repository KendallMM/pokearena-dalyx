"""Cartas: caso de uso de crear una carta, en el orden de la secuencia."""

import logging
from datetime import datetime, timedelta

from app.business.catalog.content.cards.card_image_spec import CARD_IMAGE_SPEC
from app.business.catalog.content.cards.card_rules import validate_card_data
from app.business.catalog.content.cards.models import (
    CardStatus,
    CreateCard,
    NewCard,
    PendingCard,
    StoredCard,
    ThumbnailPolicy,
    ThumbnailRun,
)
from app.business.catalog.ports import CardRepository, ImageStore
from app.business.catalog.references.reference_service import ReferenceService
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
        self._clock = clock
        self._policy = thumbnail_policy

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
        """Genera la versión pequeña de las cartas pendientes (ADR-002).

        Una carta pasa a Disponible solo cuando existen las dos versiones. Si algo
        falla, queda pendiente con el error registrado y se reintenta más tarde.
        """
        now = self._clock.now()
        pending = self._cards.claim_pending_thumbnails(
            now, self._policy.batch_size, self._policy.lease_seconds
        )
        processed = failed = 0
        for card in pending:
            try:
                self._generate_thumbnail(card)
                processed += 1
            except Exception as error:
                failed += 1
                logger.error("Falló la miniatura de %s", card.code, exc_info=True)
                self._register_failure(card, error, now)
        return ThumbnailRun(processed=processed, failed=failed)

    def _generate_thumbnail(self, card: PendingCard) -> None:
        original = self._image_store.read_original(card.image_id)
        thumbnail = self._image_processor.create_thumbnail(
            original.data, CARD_IMAGE_SPEC
        )
        self._image_store.save_thumbnail(card.image_id, thumbnail)
        # Solo ahora, con las dos versiones guardadas, la carta queda disponible.
        self._cards.mark_available(card.id)

    def _register_failure(
        self, card: PendingCard, error: Exception, now: datetime
    ) -> None:
        retry_at = now + timedelta(seconds=self._policy.retry_delay_seconds)
        try:
            self._cards.register_thumbnail_failure(card.id, str(error)[:500], retry_at)
        except Exception:
            # Si tampoco se pudo registrar, la reserva vence sola y se reintenta.
            logger.error(
                "No se pudo registrar el error de %s", card.code, exc_info=True
            )
