"""Datos de una carta dentro de la lógica de negocio."""

from dataclasses import dataclass
from enum import Enum


class CardStatus(str, Enum):
    """Estados de una carta (ADR-002)."""

    PENDING_THUMBNAIL = "pending_thumbnail"  # falta la versión pequeña
    AVAILABLE = "available"  # existen las dos versiones


@dataclass(frozen=True)
class CreateCard:
    """Solicitud de crear una carta, tal como llega del administrador."""

    name: str
    cost: int
    power: int
    card_type: str  # código del tipo, por ejemplo FUE
    rarity: str  # código de la rareza, por ejemplo COMMON
    ability: str | None  # código de la habilidad, por ejemplo HAB-000
    image_data: bytes


@dataclass(frozen=True)
class NewCard:
    """Carta lista para guardar. El código lo asigna la persistencia al guardarla."""

    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability: str
    image_id: str
    status: CardStatus
    # Nombre sin tildes ni mayúsculas, que usa la búsqueda.
    search_name: str


@dataclass(frozen=True)
class StoredCard:
    """Carta ya guardada, con su código asignado."""

    code: str
    status: CardStatus


@dataclass(frozen=True)
class PendingCard:
    """Carta reservada para generarle la versión pequeña."""

    id: int
    code: str
    image_id: str

    @property
    def label(self) -> str:
        """Texto para los registros de la tarea."""
        return self.code
