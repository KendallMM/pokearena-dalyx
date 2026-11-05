"""Contratos de identidad externa, jugadores y desafíos de inicio de sesión."""

from typing import Protocol

from app.business.identity_access.models import ExternalIdentity, Player


class IdentityVerifier(Protocol):
    """Valida la identidad externa sin acoplar las APIs al proveedor."""

    def verify(self, credential: str, nonce: str) -> ExternalIdentity:
        """Verifica firma, destinatario, vigencia y desafío del inicio de sesión."""
        ...


class PlayerRepository(Protocol):
    """Persistencia de cuentas e identidades externas."""

    def find_by_identity(self, provider: str, subject: str) -> Player | None:
        """Busca por identidad estable; nunca por correo."""
        ...

    def create(self, identity: ExternalIdentity) -> Player:
        """Crea cuenta y entrega pendiente; una carrera reutiliza la cuenta ganadora."""
        ...

    def get(self, player_id: str) -> Player:
        """Lee los datos actuales de la cuenta interna."""
        ...


class LoginChallengeStore(Protocol):
    """Desafíos efímeros de un solo uso compartidos entre instancias."""

    def create(self, nonce: str, ttl_seconds: int) -> None:
        """Guarda un desafío con vencimiento."""
        ...

    def consume(self, nonce: str) -> bool:
        """Consume atómicamente el desafío y comprueba que no haya vencido."""
        ...
