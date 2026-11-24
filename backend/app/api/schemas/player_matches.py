"""Contrato de lectura del turno inicial para un participante."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MatchLocationOut(BaseModel):
    id: int
    name: str
    description: str
    has_image: bool = False


class MatchHandCardOut(BaseModel):
    name: str
    cost: int
    power: int
    code: str | None = None
    type: str | None = None
    type_name: str | None = None
    rarity: str | None = None
    rarity_name: str | None = None
    ability_name: str | None = None


class InitialMatchResponse(BaseModel):
    id: str
    mode: Literal["ranked", "tournament", "bot"]
    turn: int
    total_turns: int
    turn_seconds: int
    deadline: datetime
    remaining_ms: int
    stake: int | None
    energy: int
    locations: list[MatchLocationOut]
    hand: list[MatchHandCardOut]
