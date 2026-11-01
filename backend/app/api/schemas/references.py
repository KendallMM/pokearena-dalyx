"""Modelos de la respuesta de referencias."""

from pydantic import BaseModel, Field


class CardTypeOut(BaseModel):
    code: str = Field(examples=["FUE"])
    name: str = Field(examples=["Fuego"])


class RarityOut(BaseModel):
    code: str = Field(examples=["COMMON"])
    name: str = Field(examples=["Común"])


class AbilityOut(BaseModel):
    code: str = Field(examples=["HAB-000"])
    name: str = Field(examples=["Sin Habilidad"])
    affected_card_type: str | None = Field(
        description="Código del tipo al que afecta. Nulo significa todos los tipos."
    )


class ReferencesResponse(BaseModel):
    """Valores que el administrador puede elegir en el formulario de cartas."""

    card_types: list[CardTypeOut]
    rarities: list[RarityOut]
    abilities: list[AbilityOut]
