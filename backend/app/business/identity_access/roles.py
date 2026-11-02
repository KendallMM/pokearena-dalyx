"""Roles del sistema y actor que realiza una solicitud."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Roles definidos para Poké-Arena."""

    PLAYER = "player"
    CONTENT_ADMIN = "content_admin"
    PARTNER_ADMIN = "partner_admin"


@dataclass(frozen=True)
class Actor:
    """Usuario autenticado que realiza la solicitud."""

    user_id: str
    role: Role
