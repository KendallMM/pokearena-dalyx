"""Datos de la búsqueda de cartas."""

from dataclasses import dataclass

from app.business.catalog.content.cards.models import CardStatus
from app.business.catalog.references.models import Ability, CardType, Rarity


@dataclass(frozen=True)
class CardSearchRequest:
    """Criterios tal como llegan del administrador. Todos son opcionales."""

    code: str | None = None
    name: str | None = None
    cost: int | None = None  # valor exacto
    cost_min: int | None = None
    cost_max: int | None = None
    power: int | None = None  # valor exacto
    power_min: int | None = None
    power_max: int | None = None
    card_type: str | None = None  # código del tipo, por ejemplo FUE
    rarity: str | None = None
    ability: str | None = None  # código de la habilidad, por ejemplo HAB-000
    limit: int | None = None  # tamaño de la página
    last_id: int | None = None  # cursor: id de la última carta de la página anterior


@dataclass(frozen=True)
class CardCriteria:
    """Criterios ya validados y normalizados. Todos los activos se cumplen a la vez."""

    code: str | None = None
    search_name: str | None = None  # sin tildes ni mayúsculas
    cost_min: int | None = None
    cost_max: int | None = None
    power_min: int | None = None
    power_max: int | None = None
    card_type: str | None = None
    rarity: str | None = None
    ability: str | None = None


@dataclass(frozen=True)
class CardSummary:
    """Una carta del resultado, con lo que el administrador necesita para revisarla."""

    id: int  # solo sirve para el cursor
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: Rarity
    ability: Ability
    status: CardStatus  # estado de la imagen: pendiente de miniatura o disponible
    thumbnail_attempts: int


@dataclass(frozen=True)
class CardPage:
    """Una página de resultados y el cursor para pedir la siguiente."""

    items: list[CardSummary]
    next_cursor: int | None  # None cuando no hay más páginas
