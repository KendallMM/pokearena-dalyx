"""Puertos del módulo Catálogo. La persistencia los implementa."""

from typing import Protocol

from app.business.catalog.references.models import Ability, CardType, Rarity


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
