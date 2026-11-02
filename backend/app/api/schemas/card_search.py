"""Modelos de la respuesta de buscar cartas."""

from pydantic import BaseModel, Field

from app.api.schemas.references import AbilityOut, CardTypeOut, RarityOut


class CardResultOut(BaseModel):
    """Una carta del resultado."""

    code: str = Field(examples=["PKA-FUE-001"])
    name: str = Field(examples=["Charmander"])
    cost: int
    power: int
    card_type: CardTypeOut
    rarity: RarityOut
    ability: AbilityOut
    image_url: str = Field(
        description="Ruta de la versión grande de la imagen.",
        examples=["/admin/cartas/PKA-FUE-001/imagen"],
    )
    image_status: str = Field(
        description="pending_thumbnail: falta la versión pequeña. available: existen las dos.",
        examples=["available"],
    )
    thumbnail_attempts: int = Field(
        description="Intentos fallidos de generar la versión pequeña."
    )


class CardSearchResponse(BaseModel):
    """Una página de resultados."""

    items: list[CardResultOut]
    next_cursor: int | None = Field(
        description="Valor de last_id para pedir la página siguiente. Nulo en la última."
    )
