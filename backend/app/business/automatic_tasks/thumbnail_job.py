"""Trabajo en segundo plano: pide a Cartas generar las miniaturas pendientes."""

import logging

from app.business.catalog.content.cards.card_service import CardService

logger = logging.getLogger(__name__)


class ThumbnailJob:
    """No cambia estados por su cuenta: pide la operación a Cartas, que aplica las reglas."""

    name = "card_thumbnails"

    def __init__(self, card_service: CardService) -> None:
        self._card_service = card_service

    def run(self) -> None:
        result = self._card_service.process_pending_thumbnails()
        if result.processed or result.failed:
            logger.info(
                "Miniaturas de cartas: %s generadas, %s con error",
                result.processed,
                result.failed,
            )
