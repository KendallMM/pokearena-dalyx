"""Puertos del módulo Catálogo. La persistencia los implementa."""

from typing import Protocol

from datetime import datetime

from app.business.catalog.content.cards.models import NewCard, PendingCard, StoredCard
from app.business.catalog.content.locations.models import (
    NewLocation,
    PendingLocation,
    StoredLocation,
)
from app.business.catalog.references.models import (
    Ability,
    CardType,
    LocationEffectType,
    Rarity,
)
from app.business.image_processing.models import ImageInfo, ProcessedImage, StoredImage


class ReferenceRepository(Protocol):
    """Lectura de los catálogos de referencia."""

    def list_card_types(self) -> list[CardType]:
        """Tipos de carta, en el orden del catálogo."""
        ...

    def list_rarities(self) -> list[Rarity]:
        """Rarezas, de la más común a la más escasa."""
        ...

    def list_abilities(self) -> list[Ability]:
        """Habilidades existentes, ordenadas por código."""
        ...

    def list_location_effect_types(self) -> list[LocationEffectType]:
        """Tipos de efecto de ubicación con los parámetros que exige cada uno."""
        ...


class CardRepository(Protocol):
    """Guardado de cartas."""

    def add(self, card: NewCard) -> StoredCard:
        """Guarda la carta y le asigna su código PKA-<TIPO>-<NNN> en una sola
        transacción. Dos creaciones simultáneas del mismo tipo reciben códigos
        distintos, y si el guardado falla no se consume ningún código."""
        ...

    def claim_pending_thumbnails(
        self, now: datetime, limit: int, lease_seconds: int
    ) -> list[PendingCard]:
        """Consulta las cartas pendientes de miniatura y las reserva por un tiempo, de
        modo que dos instancias no procesen la misma carta a la vez."""
        ...

    def mark_available(self, card_id: int) -> None:
        """Pasa la carta a Disponible. Solo afecta a cartas pendientes."""
        ...

    def register_thumbnail_failure(
        self, card_id: int, error: str, retry_at: datetime
    ) -> None:
        """Deja la carta pendiente, guarda el error y la libera para reintentar."""
        ...


class LocationRepository(Protocol):
    """Guardado de ubicaciones."""

    def add(self, location: NewLocation) -> StoredLocation:
        """Guarda la ubicación y le asigna su identificador."""
        ...

    def claim_pending_thumbnails(
        self, now: datetime, limit: int, lease_seconds: int
    ) -> list[PendingLocation]:
        """Consulta las ubicaciones pendientes de miniatura y las reserva por un
        tiempo, de modo que dos instancias no procesen la misma a la vez."""
        ...

    def mark_available(self, location_id: int) -> None:
        """Pasa la ubicación a Disponible. Solo afecta a ubicaciones pendientes."""
        ...

    def register_thumbnail_failure(
        self, location_id: int, error: str, retry_at: datetime
    ) -> None:
        """Deja la ubicación pendiente, guarda el error y la libera para reintentar."""
        ...


class ImageStore(Protocol):
    """Almacén de imágenes (base documental)."""

    def save_original(self, kind: str, data: bytes, info: ImageInfo) -> str:
        """Guarda la imagen subida por el administrador y devuelve su identificador."""
        ...

    def read_original(self, image_id: str) -> StoredImage:
        """Lee la imagen original."""
        ...

    def save_thumbnail(self, image_id: str, thumbnail: ProcessedImage) -> None:
        """Guarda la versión pequeña junto a la original. Repetirlo la reemplaza."""
        ...

    def delete(self, image_id: str) -> None:
        """Borra una imagen."""
        ...
