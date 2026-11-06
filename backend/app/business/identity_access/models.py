"""Identidad externa verificada y cuenta interna del jugador."""

from dataclasses import dataclass

from app.business.identity_access.roles import Role


@dataclass(frozen=True)
class ExternalIdentity:
    """Identidad que solo puede producir un verificador criptográfico."""

    provider: str
    subject: str
    email: str
    name: str


@dataclass(frozen=True)
class Player:
    """Cuenta interna independiente del proveedor de identidad."""

    id: str
    name: str
    email: str
    role: Role
    elo: int
    cubes: int
