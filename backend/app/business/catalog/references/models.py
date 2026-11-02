"""Valores de referencia que el administrador elige al crear contenido."""

from dataclasses import dataclass, field


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
class EffectParameter:
    """Parámetro que exige un tipo de efecto de ubicación."""

    name: str
    # integer: número entero; card_type: código de un tipo de carta existente;
    # integer_list: lista de enteros sin repetir.
    kind: str
    required: bool
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class LocationEffectType:
    """Tipo de efecto de ubicación del catálogo, con los parámetros que exige."""

    code: str
    name: str
    parameters: list[EffectParameter]


@dataclass(frozen=True)
class References:
    """Todas las referencias que cargan los formularios de contenido."""

    card_types: list[CardType]
    rarities: list[Rarity]
    abilities: list[Ability]
    location_effect_types: list[LocationEffectType] = field(default_factory=list)
