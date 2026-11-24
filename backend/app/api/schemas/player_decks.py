"""Modelos de la API de decks del jugador."""

from pydantic import BaseModel, Field

from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut


class CreateDeckRequest(BaseModel):
    name: str = Field(description="Nombre del deck, de 1 a 40 caracteres.")
    cards: list[str] = Field(description="Códigos de 12 cartas distintas.")


class DeckCreatedResponse(BaseModel):
    id: str
    name: str
    card_codes: list[str]


class DeckCardOut(BaseModel):
    code: str = Field(examples=["PKA-FUE-001"])
    name: str
    cost: int
    power: int
    card_type: CardTypeOut
    rarity: RarityOut
    ability: AbilityOut
    image_url: str = Field(description="Ruta de la versión grande de la imagen.")


class DeckOut(BaseModel):
    id: str
    name: str
    cards: list[DeckCardOut]


class DeckListResponse(BaseModel):
    items: list[DeckOut]
