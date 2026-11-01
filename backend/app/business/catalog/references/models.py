"""Valores de referencia que el administrador elige al crear contenido."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CardType:
    """Tipo elemental de una carta (por ejemplo, Fuego con código FUE)."""

    code: str
    name: str


@dataclass(frozen=True)
class Rarity:
    """Nivel de escasez de una carta."""

    code: str
    name: str


@dataclass(frozen=True)
class Ability:
    """Habilidad disponible para asignar a una carta."""

    code: str
    name: str
    # Código del tipo de carta al que afecta; None significa "todos".
    affected_card_type: str | None


@dataclass(frozen=True)
class References:
    """Todas las referencias que carga el formulario de cartas."""

    card_types: list[CardType]
    rarities: list[Rarity]
    abilities: list[Ability]
