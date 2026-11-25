"""Preparación del primer turno en la unidad de trabajo del emparejamiento."""

from datetime import timedelta
from math import comb
from typing import Any

from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.locations.location_service import LocationService
from app.business.collection.decks import DeckService
from app.business.shared.errors import ConflictError
from app.business.shared.ports import Clock, RandomSource, Transaction

TURNS = frozenset(range(1, 7))


class MatchPreparationError(ConflictError):
    """La partida aún no puede prepararse con el catálogo disponible."""


def draw(hand: list[int], deck: list[int]) -> None:
    # Si la mano está llena, la carta superior queda disponible para el próximo robo.
    if len(hand) < 7 and deck:
        hand.append(deck.pop(0))


class MatchStart:
    """Lee el catálogo vigente y conserva una copia privada para esta partida."""

    def __init__(
        self,
        decks: DeckService,
        cards: CardService,
        locations: LocationService,
        clock: Clock,
        random: RandomSource,
    ) -> None:
        self.decks = decks
        self.cards = cards
        self.locations = locations
        self.clock = clock
        self.random = random

    def prepare(
        self,
        tx: Transaction,
        mode: str,
        entries: list[tuple[str, str, list[int]]],
        bot_cards: list[int] | None = None,
    ) -> dict[str, Any]:
        decks = [
            (player, deck, self.decks.cards_for_match(tx, player, deck, snapshot))
            for player, deck, snapshot in entries
        ]
        if bot_cards is not None:
            decks.append(
                (None, None, self.decks.cards_for_match(tx, None, None, bot_cards))
            )
        # Conserva las fichas vigentes junto al estado para que el historial pueda
        # reconstruir el inicio aunque el catálogo cambie después.
        ids = {card for _, _, deck in decks for card in deck}
        cards = self.cards.match_versions(tx, ids)
        if {card["id"] for card in cards} != ids:
            raise ConflictError("No se encontraron todas las cartas de la partida.")
        locations = self.locations.match_versions(tx)
        playable = [
            location
            for location in locations
            if location["card_limit"] > 0
            and not (
                location["effect_type"] == "turn_restriction"
                and TURNS.issubset(location["effect_parameters"].get("turns", ()))
            )
        ]
        if len(locations) < 3 or len(playable) < 2:
            raise MatchPreparationError(
                "No hay tres ubicaciones disponibles con al menos dos jugables. "
                "La búsqueda sigue en espera."
            )
        playable_ids = {location["id"] for location in playable}
        restricted = [
            location for location in locations if location["id"] not in playable_ids
        ]
        all_playable = comb(len(playable), 3)
        # Cada combinación válida tiene el mismo peso, incluso si pocas ubicaciones son jugables.
        total = all_playable + comb(len(playable), 2) * len(restricted)
        if self.random.sample(range(total), 1)[0] < all_playable:
            selected = self.random.sample(playable, 3)
        else:
            selected = self.random.sample(playable, 2) + self.random.sample(
                restricted, 1
            )
        selected = self.random.sample(selected, 3)

        participants = []
        for player, deck_id, deck in decks:
            order = self.random.sample(deck, len(deck))
            # Guarda el orden completo para el historial y separa las tres cartas
            # de la mano inicial antes de aplicar el robo del turno 1.
            hand, remaining = order[:3], order[3:]
            draw(hand, remaining)
            participants.append(
                {
                    "player_id": player,
                    "deck_id": deck_id,
                    "deck_order": order,
                    "hand": hand,
                    "draw_pile": remaining,
                    "graveyard": [],
                }
            )
        # Al comenzar el tablero está vacío. Los efectos por carta propia aportan cero.
        energy = 2 + sum(
            location["extra_energy_amount"]
            for location in selected
            if location["extra_energy_mode"] == "fixed"
        )
        for participant in participants:
            participant["energy"] = energy
        now = self.clock.now()
        return {
            "mode": mode,
            "turn": 1,
            "turn_seconds": 30,
            "started_at": now.isoformat(),
            "deadline": (now + timedelta(seconds=30)).isoformat(),
            "stake": 4 if mode == "ranked" else None,
            "locations": selected,
            "cards": cards,
            "participants": participants,
        }
