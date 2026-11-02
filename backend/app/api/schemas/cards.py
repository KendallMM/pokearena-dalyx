"""Modelos de la respuesta de crear carta."""

from pydantic import BaseModel, Field


class CardAcceptedResponse(BaseModel):
    """La carta quedó registrada y su versión pequeña está en proceso."""

    code: str = Field(examples=["PKA-FUE-001"])
    status: str = Field(examples=["pending_thumbnail"])
    message: str = Field(examples=["Carta en proceso"])
