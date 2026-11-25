"""Operaciones de partida dentro de la transacción del caso de uso."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from app.business.catalog.references.reference_service import ReferenceService
from app.business.game.match_start import TURNS, MatchStart
from app.business.shared.errors import ConflictError, NotFoundError
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
    def initial_state_for(
        self, match_id: str, player_id: str
    ) -> dict[str, Any] | None: ...

    def active(self, player_id: str, tx: Transaction | None = None) -> str | None: ...
    def add(
        self,
        tx: Transaction,
        match_id: str,
        mode: str,
        entries: tuple[MatchEntry, MatchEntry],
    ) -> None: ...

    def save_initial_state(
        self, tx: Transaction, match_id: str, state: dict[str, Any]
    ) -> None: ...

    def add_bot(
        self, tx: Transaction, match_id: str, entry: MatchEntry, bot_cards: list[int]
    ) -> None: ...


class MatchOutbox(Protocol):
    def add(self, tx: Transaction, match_id: str, state: dict[str, Any]) -> None: ...


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
        self,
        repository: MatchRepository,
        players: PlayerLocks,
        searches: MatchSearches,
        preparation: MatchStart,
        outbox: MatchOutbox,
        references: ReferenceService,
    ) -> None:
        self.repository = repository
        self.players = players
        self.searches = searches
        self.preparation = preparation
        self.outbox = outbox
        self.references = references

    def active(self, player_id: str, tx: Transaction | None = None) -> str | None:
        return self.repository.active(player_id, tx)

    def initial_view(self, match_id: str, player_id: str) -> dict[str, Any]:
        """Entrega el tablero inicial y únicamente la mano del participante."""
        state = self.repository.initial_state_for(match_id, player_id)
        if state is None:
            raise NotFoundError("La partida no está disponible.")
        participant = next(
            (item for item in state["participants"] if item["player_id"] == player_id),
            None,
        )
        if participant is None:
            raise NotFoundError("La partida no está disponible.")
        # La respuesta se construye desde el estado privado y expone solo las
        # ubicaciones compartidas y los datos de juego del participante autorizado.
        cards = {card["id"]: card for card in state["cards"]}
        hand = [cards[card_id] for card_id in participant["hand"]]
        labels = {}
        if any(
            not card.get(f"{field}_name")
            for card in hand
            for field in ("type", "rarity", "ability")
        ):
            # Las partidas anteriores guardaron los códigos de las referencias.
            # Resuelve las etiquetas para la vista sin modificar el estado guardado.
            references = self.references.get_references()
            labels = {
                "type": {item.code: item.name for item in references.card_types},
                "rarity": {item.code: item.name for item in references.rarities},
                "ability": {item.code: item.name for item in references.abilities},
            }
        deadline = datetime.fromisoformat(state["deadline"])
        remaining = max(0, (deadline - self.preparation.clock.now()).total_seconds())
        return {
            "id": match_id,
            "mode": state["mode"],
            "turn": state["turn"],
            "total_turns": len(TURNS),
            "turn_seconds": state["turn_seconds"],
            "deadline": deadline,
            "remaining_ms": int(remaining * 1000),
            "stake": state["stake"],
            "energy": participant["energy"],
            "locations": [
                {
                    **{key: location[key] for key in ("id", "name", "description")},
                    "has_image": bool(location.get("image_id")),
                }
                for location in state["locations"]
            ],
            "hand": [
                {
                    **{
                        key: card.get(key)
                        for key in ("name", "cost", "power", "code", "type", "rarity")
                    },
                    **{
                        f"{field}_name": card.get(f"{field}_name")
                        or labels.get(field, {}).get(card.get(field))
                        for field in ("type", "rarity", "ability")
                    },
                }
                for card in hand
            ],
        }

    def location_image_id(self, match_id: str, player_id: str, location_id: int) -> str:
        state = self.repository.initial_state_for(match_id, player_id)
        if state is not None:
            for location in state["locations"]:
                if location["id"] == location_id and location.get("image_id"):
                    return location["image_id"]
        raise NotFoundError("La imagen de la ubicación no está disponible.")

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
        state = self.preparation.prepare(
            tx,
            first.mode,
            [(e.player_id, e.deck_id, e.card_ids) for e in (first, second)],
        )
        self.repository.add(tx, match_id, first.mode, (first, second))
        self._store_start(tx, match_id, state)
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
        bot_cards = list(opponent.card_ids)
        state = self.preparation.prepare(
            tx, "bot", [(entry.player_id, entry.deck_id, entry.card_ids)], bot_cards
        )
        self.repository.add_bot(tx, match_id, entry, bot_cards)
        self._store_start(tx, match_id, state)
        return match_id

    def _store_start(
        self, tx: Transaction, match_id: str, state: dict[str, Any]
    ) -> None:
        # La fila de emparejamiento confirma la unidad de trabajo. Si falla
        # cualquiera de estas escrituras, se revierten también la partida y la reserva.
        self.repository.save_initial_state(tx, match_id, state)
        self.outbox.add(tx, match_id, state)
