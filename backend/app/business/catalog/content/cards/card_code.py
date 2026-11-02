"""Código único e inmutable de una carta: PKA-<TIPO>-<NNN>."""

from app.business.shared.errors import ConflictError

MAX_SEQUENCE = 999  # el consecutivo tiene 3 dígitos por tipo


def build_card_code(type_code: str, number: int) -> str:
    """Arma el código, por ejemplo PKA-FUE-001. El consecutivo es por tipo."""
    if not 1 <= number <= MAX_SEQUENCE:
        raise ConflictError(
            f"Ya no hay códigos disponibles para el tipo {type_code} "
            f"(máximo {MAX_SEQUENCE})."
        )
    return f"PKA-{type_code}-{number:03d}"
