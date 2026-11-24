"""Operaciones de partida dentro de la transacción del caso de uso."""

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.business.shared.errors import ConflictError
from app.business.shared.ports import Transaction


class MatchEntry(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def player_id(self) -> str: ...
    @property
    def deck_id(self) -> str: ...
    @property
    def card_ids(self) -> list[int]: ...
    @property
    def mode(self) -> str: ...


class MatchRepository(Protocol):
    def active(self, player_id: str, tx: Transaction | None = None) -> str | None: ...
    def add(
        self,
        tx: Transaction,
        match_id: str,
        mode: str,
        entries: tuple[MatchEntry, MatchEntry],
    ) -> None: ...

    def add_bot(
        self, tx: Transaction, match_id: str, entry: MatchEntry, bot_cards: list[int]
    ) -> None: ...


class PlayerLocks(Protocol):
    def lock_players(self, tx: Transaction, player_ids: list[str]) -> None: ...


class MatchSearches(Protocol):
    def open_for_player(
        self, tx: Transaction, player_id: str
    ) -> tuple[str, str] | None: ...


@dataclass(frozen=True)
class BotOpponent:
    """Rival de una sola partida y su selección inmutable de cartas."""

    card_ids: tuple[int, ...]


class MatchService:
    """Consulta y registra partidas a través de los puertos de negocio."""

    def __init__(
        self, repository: MatchRepository, players: PlayerLocks, searches: MatchSearches
    ) -> None:
        self.repository = repository
        self.players = players
        self.searches = searches

    def active(self, player_id: str, tx: Transaction | None = None) -> str | None:
        return self.repository.active(player_id, tx)

    def create(self, tx: Transaction, first: MatchEntry, second: MatchEntry) -> str:
        """Valida a los participantes y registra la partida con sus decks."""
        if first.player_id == second.player_id or first.mode != second.mode:
            raise ConflictError(
                "Los jugadores seleccionados no forman una pareja válida."
            )
        ordered = sorted((first, second), key=lambda entry: entry.player_id)
        self.players.lock_players(tx, [entry.player_id for entry in ordered])
        # Partidas decide si la reserva corresponde. El repositorio entrega los
        # datos vigentes y registra la partida con los decks de las entradas.
        for entry in ordered:
            if self.active(entry.player_id, tx):
                raise ConflictError("Uno de los jugadores ya tiene una partida activa.")
            open_search = self.searches.open_for_player(tx, entry.player_id)
            if open_search is not None and open_search != (entry.id, "reserved"):
                raise ConflictError("Uno de los jugadores tiene una búsqueda abierta.")
        match_id = str(uuid4())
        self.repository.add(tx, match_id, first.mode, (first, second))
        return match_id

    def create_against_bot(
        self, tx: Transaction, entry: MatchEntry, opponent: BotOpponent
    ) -> str:
        """Registra al rival dentro de la partida. Solo el humano ocupa un cupo activo."""
        self.players.lock_players(tx, [entry.player_id])
        if self.active(entry.player_id, tx):
            raise ConflictError("El jugador ya tiene una partida activa.")
        if self.searches.open_for_player(tx, entry.player_id) != (entry.id, "bot"):
            raise ConflictError("La búsqueda no está reservada para el bot.")
        match_id = str(uuid4())
        self.repository.add_bot(tx, match_id, entry, list(opponent.card_ids))
        return match_id
