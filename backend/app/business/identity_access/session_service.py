"""Participante Sesiones (Identidad y Acceso): mensajes 8–33 del diagrama.

El puerto del verificador permite autenticar con otro proveedor sin cambiar
los permisos ni las credenciales internas de las APIs.
"""

from app.business.identity_access.models import Player
from app.business.identity_access.ports import IdentityVerifier, PlayerRepository


class SessionService:
    """Verifica primero la identidad y después identifica o crea al jugador."""

    def __init__(self, verifier: IdentityVerifier, players: PlayerRepository) -> None:
        self._verifier = verifier
        self._players = players

    def sign_in(self, credential: str, nonce: str) -> Player:
        """Autentica sin emitir credenciales ni coordinar las recompensas."""
        # Mensajes 9–22: un rechazo o caída del proveedor termina antes de persistir.
        identity = self._verifier.verify(credential, nonce)
        # Mensajes 23–33: el correo puede cambiar; proveedor/sub conserva la cuenta.
        player = self._players.find_by_identity(identity.provider, identity.subject)
        return player if player is not None else self._players.create(identity)
