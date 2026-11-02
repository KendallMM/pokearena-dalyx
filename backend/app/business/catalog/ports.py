"""Puertos del módulo Catálogo. La persistencia los implementa."""

from typing import Protocol

from datetime import datetime

from app.business.catalog.content.cards.models import NewCard, PendingCard, StoredCard
from app.business.catalog.references.models import Ability, CardType, Rarity
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
