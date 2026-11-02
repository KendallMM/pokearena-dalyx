"""Datos de una ubicación dentro de la lógica de negocio."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LocationStatus(str, Enum):
    """Estados de una ubicación (ADR-002, igual que las cartas)."""

    PENDING_THUMBNAIL = "pending_thumbnail"  # falta la versión pequeña
    AVAILABLE = "available"  # existen las dos versiones


class ExtraEnergyMode(str, Enum):
    """Modalidades de energía extra por turno."""

    FIXED = "fixed"  # un monto fijo para cada jugador
    PER_CARD = "per_card"  # un monto por cada carta propia en la ubicación


@dataclass(frozen=True)
class CreateLocation:
    """Solicitud de crear una ubicación, tal como llega del administrador."""

    name: str
    description: str
    card_limit: int
    extra_energy_mode: str
    extra_energy_amount: int
    effect_type: str | None  # código del tipo de efecto; None significa sin efecto
    effect_parameters: dict[str, Any] | None
    image_data: bytes


@dataclass(frozen=True)
class NewLocation:
    """Ubicación lista para guardar."""

    name: str
    description: str
    card_limit: int
    extra_energy_mode: ExtraEnergyMode
    extra_energy_amount: int
    effect_type: str | None
    effect_parameters: dict[str, Any]  # ya validados y normalizados
    image_id: str
    status: LocationStatus


@dataclass(frozen=True)
class StoredLocation:
    """Ubicación ya guardada."""

    id: int
    status: LocationStatus


@dataclass(frozen=True)
class PendingLocation:
    """Ubicación reservada para generarle la versión pequeña."""

    id: int
    image_id: str

    @property
    def label(self) -> str:
        """Texto para los registros de la tarea."""
        return f"ubicación {self.id}"
