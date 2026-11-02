"""Modelos de la respuesta de crear ubicación."""

from pydantic import BaseModel, Field


class LocationAcceptedResponse(BaseModel):
    """La ubicación quedó registrada y su versión pequeña está en proceso."""

    id: int = Field(examples=[1])
    status: str = Field(examples=["pending_thumbnail"])
    message: str = Field(examples=["Ubicación en proceso"])
