"""Modelos de respuesta de la API de ubicaciones."""

from pydantic import BaseModel

# ======================================================================
# Ubicaciones
# ======================================================================


class LocationCreationResponse(BaseModel):
    id: int
    version: int
    status: str
    status_url: str


class LocationStatusResponse(BaseModel):
    id: int
    version: int
    status: str
    image_processing: str | None
