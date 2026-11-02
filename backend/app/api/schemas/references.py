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


class EffectParameterOut(BaseModel):
    name: str = Field(examples=["amount"])
    kind: str = Field(
        description="integer, card_type o integer_list", examples=["integer"]
    )
    required: bool
    minimum: int | None = Field(description="Mínimo permitido, si aplica.")
    maximum: int | None = Field(description="Máximo permitido, si aplica.")


class LocationEffectTypeOut(BaseModel):
    code: str = Field(examples=["type_bonus"])
    name: str = Field(examples=["Bonificación por tipo"])
    parameters: list[EffectParameterOut]


class ReferencesResponse(BaseModel):
    """Valores que el administrador puede elegir en los formularios de contenido."""

    card_types: list[CardTypeOut]
    rarities: list[RarityOut]
    abilities: list[AbilityOut]
    location_effect_types: list[LocationEffectTypeOut]
