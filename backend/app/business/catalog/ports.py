"""Puertos del módulo Catálogo. La persistencia los implementa."""

from typing import Protocol

from app.business.catalog.content.cards.models import NewCard, StoredCard
from app.business.catalog.references.models import Ability, CardType, Rarity
from app.business.image_processing.models import ImageInfo


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


class ImageStore(Protocol):
    """Almacén de imágenes (base documental)."""

    def save_original(self, kind: str, data: bytes, info: ImageInfo) -> str:
        """Guarda la imagen subida por el administrador y devuelve su identificador."""
        ...

    def delete(self, image_id: str) -> None:
        """Borra una imagen."""
        ...
