"""Copia al historial los eventos confirmados en la base relacional."""

import logging
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Any, Protocol

from app.business.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingMatchEvent:
    id: str
    match_id: str
    payload: dict[str, Any]
    created_at: datetime


class PendingMatchEvents(Protocol):
    def next_pending(
        self, after: PendingMatchEvent | None
    ) -> PendingMatchEvent | None: ...
    def mark_copied(self, event_id: str) -> None: ...


class MatchHistory(Protocol):
    def store(self, event: PendingMatchEvent, timeout_seconds: float) -> None: ...


class MatchEventsJob:
    name = "match_events"

    def __init__(
        self, pending: PendingMatchEvents, history: MatchHistory, cycle_seconds: float
    ) -> None:
        self.pending = pending
        self.history = history
        self.cycle_seconds = cycle_seconds

    def run(self) -> None:
        # Una pasada cede el hilo compartido cuando consume su intervalo.
        deadline = monotonic() + self.cycle_seconds
        previous = None
        while monotonic() < deadline:
            event = self.pending.next_pending(previous)
            if event is None:
                return
            # Avanza el cursor aunque falle una copia, para intentar otros eventos.
            # La próxima pasada vuelve a leer los que sigan pendientes.
            previous = event
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            try:
                self.history.store(event, remaining)
                # Si falla el marcado, el mismo ID permite confirmar la copia en el reintento.
                self.pending.mark_copied(event.id)
            except ServiceUnavailableError:
                logger.warning("El evento de partida %s sigue pendiente", event.id)
