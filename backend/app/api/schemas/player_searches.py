"""Contratos de búsqueda de partida."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SearchRequest(BaseModel):
    """Deck elegido por el jugador para entrar a la fila."""

    model_config = ConfigDict(extra="forbid")
    deck_id: str | None = None


class SearchResponse(BaseModel):
    """Estado de la búsqueda y, cuando se encuentra, su partida asignada."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    deck_id: str
    mode: Literal["ranked", "tournament"]
    status: Literal["waiting", "reserved", "found", "cancelled"]
    created_at: datetime
    match_id: str | None
    error: str | None
