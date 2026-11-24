"""Fila clasificatoria y coordinación del emparejamiento."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from app.business.collection.decks import DeckService
from app.business.game.matches import MatchService
from app.business.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from app.business.shared.ports import Clock, Transaction, TransactionManager

logger = logging.getLogger(__name__)
MIN_CUBES = 8
INITIAL_RANGE = 100
RANGE_INCREMENT = 50
RANGE_INTERVAL = 10
MAX_RANGE = 400
MATCH_FAILURE = "No se pudo crear la partida. La búsqueda sigue en espera."


@dataclass(frozen=True)
class Search:
    id: str
    player_id: str
    deck_id: str
    card_ids: list[int]
    elo: int
    mode: str
    status: str
    created_at: datetime
    match_id: str | None = None
    error: str | None = None


class SearchRepository(Protocol):
    def operation(
        self, tx: Transaction, player_id: str, key_hash: str
    ) -> Search | None: ...
    def record_operation(
        self, tx: Transaction, search: Search, key_hash: str
    ) -> None: ...
    def add(self, tx: Transaction, search: Search) -> Search: ...
    def current(self, player_id: str) -> Search | None: ...
    def get(self, player_id: str, search_id: str) -> Search | None: ...
    def cancel(
        self, tx: Transaction, player_id: str, search_id: str
    ) -> Search | None: ...
    def waiting(self) -> list[Search]: ...
    def reserve(self, tx: Transaction, ids: tuple[str, str]) -> int: ...
    def found(self, tx: Transaction, ids: tuple[str, str], match_id: str) -> int: ...
    def record_failure(self, ids: tuple[str, str], message: str) -> None: ...


class QueuePlayers(Protocol):
    def lock_players(self, tx: Transaction, player_ids: list[str]) -> None: ...
    def elo(self, tx: Transaction, player_id: str) -> int: ...


class CubeBalances(Protocol):
    def balance(self, tx: Transaction, player_id: str) -> int: ...


def elo_range(seconds: float) -> int:
    return min(
        MAX_RANGE,
        INITIAL_RANGE + RANGE_INCREMENT * int(max(0, seconds) // RANGE_INTERVAL),
    )


def compatible_pairs(
    waiting: list[Search], now: datetime
) -> list[tuple[Search, Search]]:
    """Prioriza las búsquedas antiguas y respeta el rango de Elo de ambos jugadores."""
    ordered = sorted(waiting, key=lambda search: (search.created_at, search.id))
    ranges = {
        search.id: elo_range((now - search.created_at).total_seconds())
        for search in ordered
    }
    paired: set[str] = set()
    pairs = []
    for index, search in enumerate(ordered):
        if search.player_id in paired:
            continue
        candidates = (
            rival
            for rival in ordered[index + 1 :]
            if rival.player_id != search.player_id
            and rival.player_id not in paired
            and abs(search.elo - rival.elo) <= min(ranges[search.id], ranges[rival.id])
        )
        rival = min(
            candidates, key=lambda other: abs(search.elo - other.elo), default=None
        )
        if rival is not None:
            pairs.append((search, rival))
            paired.update((search.player_id, rival.player_id))
    return pairs


class EloQueue:
    """Gestiona el ingreso a la fila y coordina la creación de partidas."""

    def __init__(
        self,
        searches: SearchRepository,
        decks: DeckService,
        matches: MatchService,
        players: QueuePlayers,
        cubes: CubeBalances,
        transactions: TransactionManager,
        clock: Clock,
    ) -> None:
        self.searches = searches
        self.decks = decks
        self.matches = matches
        self.players = players
        self.cubes = cubes
        self.transactions = transactions
        self.clock = clock

    def enter(
        self,
        player_id: str,
        deck_id: str | None,
        *,
        mode: str = "ranked",
        key_hash: str | None = None,
    ) -> tuple[Search, bool]:
        """Valida el ingreso y devuelve la búsqueda nueva o vigente."""
        deck_id = deck_id.strip() if deck_id else ""
        with self.transactions.begin() as tx:
            # El bloqueo serializa el ingreso con la creación de partidas.
            # MySQL conserva la operación incluso si se pierde la respuesta en Redis.
            self.players.lock_players(tx, [player_id])
            if key_hash is not None:
                previous = self.searches.operation(tx, player_id, key_hash)
                if previous is not None:
                    if previous.mode != mode or previous.deck_id != deck_id:
                        raise ConflictError(
                            "La clave de operación ya pertenece a otra solicitud.",
                            "Idempotency-Key",
                        )
                    return previous, False
            cards = []
            deck_error = None
            if deck_id:
                try:
                    cards = self.decks.validate_for_play(tx, player_id, deck_id)
                except (NotFoundError, ValidationFailedError) as error:
                    deck_error = error
            match_id = self.matches.active(player_id, tx)
            balance = self.cubes.balance(tx, player_id)
            elo = self.players.elo(tx, player_id)
            # Los errores del deck tienen prioridad sobre la partida activa y el saldo.
            if not deck_id:
                raise ValidationFailedError(
                    "Selecciona un deck para buscar partida.", "deck_id"
                )
            if deck_error is not None:
                raise deck_error
            if match_id:
                raise ConflictError(f"Ya estás en la partida activa {match_id}.")
            if mode == "ranked" and balance < MIN_CUBES:
                raise ValidationFailedError(
                    f"Tienes {balance} cubos. Necesitas al menos {MIN_CUBES} para buscar partida clasificatoria. Compra cubos para continuar.",
                    "cubes",
                )
            proposed = Search(
                str(uuid4()),
                player_id,
                deck_id,
                cards,
                elo,
                mode,
                "waiting",
                self.clock.now(),
            )
            search = self.searches.add(tx, proposed)
            if search.mode != mode or search.deck_id != deck_id:
                name = "clasificatoria" if search.mode == "ranked" else "de torneo"
                logger.info("Conflicto con la búsqueda %s", search.id)
                raise ConflictError(
                    f"La búsqueda vigente {search.id} es {name} y usa el deck {search.deck_id}. Sal de esa búsqueda antes de continuar.",
                    "deck_id",
                )
            if key_hash is not None:
                self.searches.record_operation(tx, search, key_hash)
        created = search.id == proposed.id
        logger.info("Búsqueda %s %s", search.id, "creada" if created else "reutilizada")
        return search, created

    def current(self, player_id: str) -> Search | None:
        return self.searches.current(player_id)

    def get(self, player_id: str, search_id: str) -> Search:
        return self._require(self.searches.get(player_id, search_id))

    def cancel(self, player_id: str, search_id: str) -> Search:
        with self.transactions.begin() as tx:
            self.players.lock_players(tx, [player_id])
            return self._require(self.searches.cancel(tx, player_id, search_id))

    @staticmethod
    def _require(search: Search | None) -> Search:
        if search is None:
            raise NotFoundError("La búsqueda no existe.", "search_id")
        return search

    def match_waiting(self) -> None:
        """Lee la fila y procesa las parejas compatibles que encuentre."""
        logger.debug("Inicio del trabajo de emparejamiento clasificatorio")
        pairs = compatible_pairs(self.searches.waiting(), self.clock.now())
        logger.debug("Emparejamiento clasificatorio: %d parejas candidatas", len(pairs))
        for first, second in pairs:
            self.match_pair(first, second)
        logger.debug(
            "Fin del trabajo de emparejamiento: %d parejas procesadas", len(pairs)
        )

    def match_pair(self, first: Search, second: Search) -> None:
        """Reserva la pareja y registra su partida en la misma transacción."""
        ids = (first.id, second.id)
        try:
            with self.transactions.begin() as tx:
                # Bloquea a los jugadores antes de reservar para serializar el
                # emparejamiento con el ingreso a la fila y la cancelación.
                self.players.lock_players(
                    tx, sorted((first.player_id, second.player_id))
                )
                if self.searches.reserve(tx, ids) != 2:
                    tx.rollback()
                    logger.info("Pareja descartada por concurrencia: %s, %s", *ids)
                    return
                # El gestor confirma al salir del bloque si se actualizaron las dos filas.
                match_id = self.matches.create(tx, first, second)
                if self.searches.found(tx, ids, match_id) != 2:
                    raise RuntimeError("La pareja no actualizó las dos búsquedas")
        except Exception as error:
            # Guarda el diagnóstico en una transacción aparte para que sobreviva
            # al rollback de la reserva y la creación de la partida.
            logger.warning(
                "Transacción interrumpida para %s y %s (%s)", *ids, type(error).__name__
            )
            try:
                # Una desconexión durante COMMIT puede dejar la partida confirmada.
                confirmed = self.searches.get(first.player_id, first.id)
                rival = self.searches.get(second.player_id, second.id)
                if (
                    confirmed
                    and rival
                    and confirmed.match_id
                    and confirmed.match_id == rival.match_id
                ):
                    logger.info("Partida %s confirmada en MySQL", confirmed.match_id)
                    return
                message = (
                    error.message if isinstance(error, ConflictError) else MATCH_FAILURE
                )
                self.searches.record_failure(ids, message)
            except Exception as recovery_error:
                logger.warning(
                    "No se pudo comprobar el emparejamiento (%s)",
                    type(recovery_error).__name__,
                )
            return
        logger.info("Partida %s confirmada para %s y %s", match_id, *ids)
