"""Ubicaciones: caso de uso de crear una ubicación."""

import logging

from app.business.catalog.content.locations.location_image_spec import (
    LOCATION_IMAGE_SPEC,
)
from app.business.catalog.content.locations.location_rules import (
    validate_extra_energy,
    validate_location_data,
)
from app.business.catalog.content.locations.models import (
    CreateLocation,
    LocationStatus,
    NewLocation,
    StoredLocation,
)
from app.business.catalog.ports import ImageStore, LocationRepository
from app.business.catalog.references.reference_service import ReferenceService
from app.business.catalog.thumbnails import (
    ThumbnailGenerator,
    ThumbnailPolicy,
    ThumbnailRun,
)
from app.business.image_processing.image_processor import ImageProcessor
from app.business.shared.ports import Clock

logger = logging.getLogger(__name__)


class LocationService:
    """Coordina las reglas de ubicación, referencias, imagen y guardado."""

    def __init__(
        self,
        references: ReferenceService,
        image_processor: ImageProcessor,
        image_store: ImageStore,
        locations: LocationRepository,
        clock: Clock,
        thumbnail_policy: ThumbnailPolicy = ThumbnailPolicy(),
    ) -> None:
        self._references = references
        self._image_processor = image_processor
        self._image_store = image_store
        self._locations = locations
        self._thumbnails = ThumbnailGenerator(
            tracking=locations,
            image_processor=image_processor,
            image_store=image_store,
            clock=clock,
            spec=LOCATION_IMAGE_SPEC,
            policy=thumbnail_policy,
        )

    def create_location(self, command: CreateLocation) -> StoredLocation:
        """Valida todo antes de guardar nada. La ubicación queda pendiente de miniatura."""
        validate_location_data(command.name, command.description, command.card_limit)
        energy_mode = validate_extra_energy(
            command.extra_energy_mode, command.extra_energy_amount
        )
        effect_parameters = self._references.validate_location_effect(
            command.effect_type, command.effect_parameters
        )
        image_info = self._image_processor.validate(
            command.image_data, LOCATION_IMAGE_SPEC
        )

        # Primero la imagen, luego el registro (ver ADR-002).
        image_id = self._image_store.save_original(
            "location", command.image_data, image_info
        )
        try:
            return self._locations.add(
                NewLocation(
                    name=command.name.strip(),
                    description=command.description.strip(),
                    card_limit=command.card_limit,
                    extra_energy_mode=energy_mode,
                    extra_energy_amount=command.extra_energy_amount,
                    effect_type=command.effect_type or None,
                    effect_parameters=effect_parameters,
                    image_id=image_id,
                    status=LocationStatus.PENDING_THUMBNAIL,
                )
            )
        except Exception:
            self._discard_image(image_id)
            raise

    def _discard_image(self, image_id: str) -> None:
        """Si no se pudo guardar la ubicación, intenta no dejar la imagen huérfana."""
        try:
            self._image_store.delete(image_id)
        except Exception:
            logger.error(
                "No se pudo borrar la imagen huérfana %s", image_id, exc_info=True
            )

    def process_pending_thumbnails(self) -> ThumbnailRun:
        """Genera la versión pequeña de las ubicaciones pendientes (ADR-002)."""
        return self._thumbnails.run()
