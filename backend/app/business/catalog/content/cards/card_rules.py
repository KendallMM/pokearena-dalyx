"""Reglas de los datos de una carta (historia Crear carta)."""

from app.business.shared.errors import ValidationFailedError

MIN_COST, MAX_COST = 0, 10
MIN_POWER, MAX_POWER = -20, 20  # una carta puede restar poder a su ubicación
MAX_NAME_LENGTH = 100  # límite del almacenamiento; la historia no fija uno


def validate_card_data(name: str, cost: int, power: int) -> None:
    """Lanza ValidationFailedError indicando el campo inválido."""
    if not name.strip():
        raise ValidationFailedError("El nombre es obligatorio.", field="name")
    if len(name.strip()) > MAX_NAME_LENGTH:
        raise ValidationFailedError(
            f"El nombre no puede superar {MAX_NAME_LENGTH} caracteres.", field="name"
        )
    if not MIN_COST <= cost <= MAX_COST:
        raise ValidationFailedError(
            f"El costo debe estar entre {MIN_COST} y {MAX_COST}.", field="cost"
        )
    if not MIN_POWER <= power <= MAX_POWER:
        raise ValidationFailedError(
            f"El poder debe estar entre {MIN_POWER} y {MAX_POWER}.", field="power"
        )
