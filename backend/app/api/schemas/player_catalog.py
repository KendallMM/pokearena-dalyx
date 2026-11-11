"""Modelos de la respuesta del catálogo que ve el jugador."""

from pydantic import BaseModel, Field

from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut


class PlayerCardOut(BaseModel):
    """Una carta del catálogo y cuántas copias tiene el jugador."""

    code: str = Field(examples=["PKA-FUE-001"])
    name: str = Field(examples=["Charmander"])
    cost: int
    power: int
    card_type: CardTypeOut
    rarity: RarityOut
    ability: AbilityOut
    image_url: str = Field(
        description="Ruta de la versión grande de la imagen.",
        examples=["/v1/cartas/PKA-FUE-001/imagen"],
    )
    owned: bool = Field(description="Verdadero si el jugador posee la carta.")
    copies: int = Field(description="Copias que posee el jugador; 0 si no la tiene.")


class PlayerCatalogResponse(BaseModel):
    """Una página del catálogo."""

    items: list[PlayerCardOut]
    next_cursor: int | None = Field(
        description="Valor de last_id para pedir la página siguiente. Nulo en la última."
    )
