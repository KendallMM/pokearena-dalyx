"""Invoca el emparejamiento en segundo plano."""

from app.business.matchmaking.elo_queue import EloQueue


class MatchmakingJob:
    name = "ranked_matchmaking"

    def __init__(self, queue: EloQueue) -> None:
        self.queue = queue

    def run(self) -> None:
        """Pide a Fila por Elo que procese las búsquedas en espera."""
        self.queue.match_waiting()
