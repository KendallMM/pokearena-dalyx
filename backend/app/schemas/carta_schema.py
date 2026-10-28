"""Modelos de respuesta de la API de cartas (y formato de error común)."""

from typing import Any

from pydantic import BaseModel

# ======================================================================
# Formato de error
# ======================================================================


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ======================================================================
# Cartas
# ======================================================================


class CardCreationResponse(BaseModel):
    code: str
    status: str
    status_url: str


class CardAbilityOut(BaseModel):
    code: str
    name: str
    trigger_type: str | None
    condition_type: str | None
    effect_type: str | None
    target_type: str | None
    affected_type: str | None
    parameters: dict[str, Any]


class CardImageLinks(BaseModel):
    large: str
    small: str


class CardSummary(BaseModel):
    code: str
    name: str
    cost: int
    power: int
    type: str
    rarity: str
    status: str
    ability: CardAbilityOut
    image: CardImageLinks | None


class CardSearchResponse(BaseModel):
    items: list[CardSummary]
    next_cursor: str | None
    has_more: bool


class CardStatusAbility(BaseModel):
    code: str
    affected_type: str | None


class CardStatusResponse(BaseModel):
    code: str
    status: str
    image_processing: str | None
    ability: CardStatusAbility
