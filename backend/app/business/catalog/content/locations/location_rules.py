"""Reglas de los datos de una ubicación (historia Crear ubicación)."""

from app.business.catalog.content.locations.models import ExtraEnergyMode
from app.business.shared.errors import ValidationFailedError

MIN_CARD_LIMIT, MAX_CARD_LIMIT = 0, 5  # 0 significa que no se pueden jugar cartas
MAX_NAME_LENGTH = 100  # límite del almacenamiento; la historia no fija uno
MAX_DESCRIPTION_LENGTH = 500  # ídem

# Monto máximo de energía extra según la modalidad (el mínimo es 0).
MAX_EXTRA_ENERGY = {
    ExtraEnergyMode.FIXED: 3,  # por jugador, al inicio de cada turno
    ExtraEnergyMode.PER_CARD: 2,  # por cada carta propia en la ubicación
}


def validate_location_data(name: str, description: str, card_limit: int) -> None:
    """Lanza ValidationFailedError indicando el campo inválido."""
    if not name.strip():
        raise ValidationFailedError("El nombre es obligatorio.", field="name")
    if len(name.strip()) > MAX_NAME_LENGTH:
        raise ValidationFailedError(
            f"El nombre no puede superar {MAX_NAME_LENGTH} caracteres.", field="name"
        )
    if not description.strip():
        raise ValidationFailedError(
            "La descripción es obligatoria.", field="description"
        )
    if len(description.strip()) > MAX_DESCRIPTION_LENGTH:
        raise ValidationFailedError(
            f"La descripción no puede superar {MAX_DESCRIPTION_LENGTH} caracteres.",
            field="description",
        )
    if not MIN_CARD_LIMIT <= card_limit <= MAX_CARD_LIMIT:
        raise ValidationFailedError(
            f"El límite de cartas debe estar entre {MIN_CARD_LIMIT} y {MAX_CARD_LIMIT}.",
            field="card_limit",
        )


def validate_extra_energy(mode: str, amount: int) -> ExtraEnergyMode:
    """Valida la modalidad y el monto, y devuelve la modalidad ya reconocida."""
    try:
        energy_mode = ExtraEnergyMode(mode)
    except ValueError:
        allowed = ", ".join(m.value for m in ExtraEnergyMode)
        raise ValidationFailedError(
            f"La modalidad de energía extra no existe. Use una de: {allowed}.",
            field="extra_energy_mode",
        ) from None
    maximum = MAX_EXTRA_ENERGY[energy_mode]
    if not 0 <= amount <= maximum:
        raise ValidationFailedError(
            f"El monto de energía extra debe estar entre 0 y {maximum} "
            f"en la modalidad {energy_mode.value}.",
            field="extra_energy_amount",
        )
    return energy_mode
