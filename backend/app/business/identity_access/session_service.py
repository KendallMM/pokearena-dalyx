"""Autenticación de jugadores mediante un verificador externo."""

from app.business.identity_access.models import Player
from app.business.identity_access.ports import IdentityVerifier, PlayerRepository


class SessionService:
    """Verifica primero la identidad y después identifica o crea al jugador."""

    def __init__(self, verifier: IdentityVerifier, players: PlayerRepository) -> None:
        self._verifier = verifier
        self._players = players

    def sign_in(self, credential: str, nonce: str) -> Player:
        """Autentica sin emitir credenciales ni coordinar las recompensas."""
        identity = self._verifier.verify(credential, nonce)
        player = self._players.find_by_identity(identity.provider, identity.subject)
        return player if player is not None else self._players.create(identity)
