"""Prepara el deck de un rival automático para una partida."""

from collections.abc import Sequence
from typing import Protocol

from app.business.collection.decks import DECK_SIZE
from app.business.game.matches import BotOpponent
from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import RandomSource, Transaction


class AvailableBotCards(Protocol):
    def available_ids(
        self, transaction: Transaction, rarity_code: str
    ) -> Sequence[int]: ...


class Bot:
    def __init__(self, cards: AvailableBotCards, random: RandomSource) -> None:
        self.cards = cards
        self.random = random

    def prepare(self, tx: Transaction) -> BotOpponent:
        candidates = sorted(set(self.cards.available_ids(tx, "COMMON")))
        if len(candidates) < DECK_SIZE:
            raise ServiceUnavailableError(
                "Todavía no hay cartas suficientes para preparar al bot."
            )
        return BotOpponent(tuple(self.random.sample(candidates, DECK_SIZE)))
