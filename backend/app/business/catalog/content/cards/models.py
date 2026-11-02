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
