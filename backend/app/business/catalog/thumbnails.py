"""Generación de la versión pequeña, compartida por Cartas y Ubicaciones (ADR-002)."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.business.catalog.ports import ImageStore
from app.business.image_processing.image_processor import ImageProcessor
from app.business.image_processing.models import ImageSpec
from app.business.shared.ports import Clock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThumbnailPolicy:
    """Parámetros de la tarea de miniaturas. Los define el ADR de tareas automáticas."""

    batch_size: int = 20
    lease_seconds: int = 120
    retry_delay_seconds: int = 60


@dataclass(frozen=True)
class ThumbnailRun:
    """Resultado de una pasada de la tarea."""

    processed: int
    failed: int


class PendingThumbnail(Protocol):
    """Elemento reservado para generarle la versión pequeña."""

    @property
    def id(self) -> int: ...

    @property
    def image_id(self) -> str: ...

    @property
    def label(self) -> str:
        """Texto para los registros (por ejemplo, el código de la carta)."""
        ...


class ThumbnailTracking(Protocol):
    """Seguimiento de miniaturas que debe ofrecer el repositorio de cada contenido."""

    def claim_pending_thumbnails(
        self, now: datetime, limit: int, lease_seconds: int
    ) -> list[PendingThumbnail]:
        """Consulta los pendientes y los reserva por un tiempo, de modo que dos
        instancias no procesen el mismo a la vez."""
        ...

    def mark_available(self, item_id: int) -> None:
        """Pasa el elemento a Disponible. Solo afecta a los pendientes."""
        ...

    def register_thumbnail_failure(
        self, item_id: int, error: str, retry_at: datetime
    ) -> None:
        """Deja el elemento pendiente, guarda el error y lo libera para reintentar."""
        ...


class ThumbnailGenerator:
    """Genera la versión pequeña de los pendientes de un tipo de contenido.

    Un elemento pasa a Disponible solo cuando existen las dos versiones. Si algo
    falla, queda pendiente con el error registrado y se reintenta más tarde.
    """

    def __init__(
        self,
        tracking: ThumbnailTracking,
        image_processor: ImageProcessor,
        image_store: ImageStore,
        clock: Clock,
        spec: ImageSpec,
        policy: ThumbnailPolicy,
    ) -> None:
        self._tracking = tracking
        self._image_processor = image_processor
        self._image_store = image_store
        self._clock = clock
        self._spec = spec
        self._policy = policy

    def run(self) -> ThumbnailRun:
        now = self._clock.now()
        pending = self._tracking.claim_pending_thumbnails(
            now, self._policy.batch_size, self._policy.lease_seconds
        )
        processed = failed = 0
        for item in pending:
            try:
                self._generate(item)
                processed += 1
            except Exception as error:
                failed += 1
                logger.error("Falló la miniatura de %s", item.label, exc_info=True)
                self._register_failure(item, error, now)
        return ThumbnailRun(processed=processed, failed=failed)

    def _generate(self, item: PendingThumbnail) -> None:
        original = self._image_store.read_original(item.image_id)
        thumbnail = self._image_processor.create_thumbnail(original.data, self._spec)
        self._image_store.save_thumbnail(item.image_id, thumbnail)
        # Solo ahora, con las dos versiones guardadas, queda disponible.
        self._tracking.mark_available(item.id)

    def _register_failure(
        self, item: PendingThumbnail, error: Exception, now: datetime
    ) -> None:
        retry_at = now + timedelta(seconds=self._policy.retry_delay_seconds)
        try:
            self._tracking.register_thumbnail_failure(
                item.id, str(error)[:500], retry_at
            )
        except Exception:
            # Si tampoco se pudo registrar, la reserva vence sola y se reintenta.
            logger.error(
                "No se pudo registrar el error de %s", item.label, exc_info=True
            )
