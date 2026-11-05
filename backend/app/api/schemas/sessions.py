"""Contrato público de autenticación y datos de la cuenta interna."""

from datetime import datetime

from pydantic import BaseModel

from app.business.collection.initial_collection import DeliveryStatus
from app.business.identity_access.roles import Role


class GoogleLoginRequest(BaseModel):
    """Token de identidad; nunca se usa para autorizar las APIs del juego."""

    credential: str


class GoogleChallengeResponse(BaseModel):
    """Configuración pública y nonce vinculado al navegador mediante cookie."""

    client_id: str
    nonce: str
    expires_in: int


class PlayerResponse(BaseModel):
    """Datos propios de Poké-Arena, sin identidad externa ni secretos."""

    id: str
    name: str
    email: str
    role: Role
    elo: int
    cubes: int


class CollectionDeliveryResponse(BaseModel):
    """Resultado de la entrega inicial, independiente del éxito de autenticación."""

    status: DeliveryStatus
    message: str


class SessionResponse(BaseModel):
    """Credenciales internas y resultado del inicio de sesión."""

    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime
    player: PlayerResponse
    initial_collection: CollectionDeliveryResponse
