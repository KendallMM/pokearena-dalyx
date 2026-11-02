"""Trabajo en segundo plano: pide generar las miniaturas pendientes."""

import logging
from typing import Protocol

from app.business.catalog.thumbnails import ThumbnailRun

logger = logging.getLogger(__name__)


class ThumbnailService(Protocol):
    """Servicio de contenido que sabe generar sus propias miniaturas."""

    def process_pending_thumbnails(self) -> ThumbnailRun: ...


class ThumbnailJob:
    """No cambia estados por su cuenta: pide la operación al servicio del contenido
    (Cartas o Ubicaciones), que aplica las reglas."""

    def __init__(
        self, service: ThumbnailService, name: str = "card_thumbnails"
    ) -> None:
        self.name = name
        self._service = service

    def run(self) -> None:
        result = self._service.process_pending_thumbnails()
        if result.processed or result.failed:
            logger.info(
                "Trabajo %s: %s generadas, %s con error",
                self.name,
                result.processed,
                result.failed,
            )
