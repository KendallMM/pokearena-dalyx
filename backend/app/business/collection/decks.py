"""Participante Mazos (Colección y Mazos): historia Crear un deck.

Las comprobaciones se hacen en orden y se responde con el primer fallo: nombre,
cantidad, repetidas y posesión. El jugador siempre sale de las credenciales.
"""

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from app.business.catalog.content.cards.card_directory import CardDirectory
from app.business.catalog.search.models import CardSummary
from app.business.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from app.business.shared.text import normalize_for_search

DECK_SIZE = 12
MAX_DECK_NAME_LENGTH = 40


class DeckNameConflictError(ConflictError):
    """El jugador ya tiene un deck con ese nombre."""

    def __init__(self, name: str) -> None:
        super().__init__(f'Ya tienes un deck llamado "{name}".', field="name")


@dataclass(frozen=True)
class StoredDeck:
    """Un deck guardado, con los identificadores de sus cartas."""

    id: str
    name: str
    card_ids: list[int]


@dataclass(frozen=True)
class CreatedDeck:
    id: str
    name: str
    card_codes: list[str]


@dataclass(frozen=True)
class Deck:
    """Un deck con los datos de sus cartas."""

    id: str
    name: str
    cards: list[CardSummary]


class DeckRepository(Protocol):
    """Repositorio de mazos."""

    def add(
        self, player_id: str, name: str, name_key: str, card_ids: list[int]
    ) -> StoredDeck:
        """Guarda el deck y sus cartas en una transacción.

        Lanza DeckNameConflictError si el jugador ya tiene ese nombre.
        """
        ...

    def list_for(self, player_id: str) -> list[StoredDeck]:
        """Decks de ese jugador."""
        ...

    def get_for(self, deck_id: str, player_id: str) -> StoredDeck | None:
        """El deck, solo si pertenece a ese jugador."""
        ...


class DeckCollection(Protocol):
    """Repositorio de colección: qué cartas posee el jugador."""

    def copies_of(self, player_id: str, card_ids: list[int]) -> dict[int, int]:
        """Copias de esas cartas; las que no posee no aparecen."""
        ...


def clean_deck_name(name: str) -> str:
    """Quita los espacios sobrantes y valida el largo."""
    cleaned = " ".join(name.split())
    if not normalize_for_search(cleaned) or len(cleaned) > MAX_DECK_NAME_LENGTH:
        raise ValidationFailedError(
            f"El nombre del deck debe tener entre 1 y {MAX_DECK_NAME_LENGTH} "
            "caracteres.",
            field="name",
        )
    return cleaned


def deck_name_key(name: str) -> str:
    """Clave del nombre: igual sin importar mayúsculas, tildes ni espacios.

    Es un hash de largo fijo porque normalizar puede alargar algunos caracteres.
    """
    return hashlib.sha256(normalize_for_search(name).encode()).hexdigest()


def clean_card_codes(codes: list[str]) -> list[str]:
    """Valida cantidad y repetidas, antes de consultar la base de datos."""
    cleaned = [code.strip().upper() for code in codes]
    if len(cleaned) != DECK_SIZE:
        raise ValidationFailedError(
            f"Un deck debe tener exactamente {DECK_SIZE} cartas; "
            f"este tiene {len(cleaned)}.",
            field="cards",
        )
    repeated = [code for code, count in Counter(cleaned).items() if count > 1]
    if repeated:
        raise ValidationFailedError(
            f"Hay cartas repetidas: {', '.join(repeated)}.", field="cards"
        )
    return cleaned


class DeckService:
    """Crea y consulta los decks del jugador autenticado."""

    def __init__(
        self,
        decks: DeckRepository,
        cards: CardDirectory,
        collection: DeckCollection,
    ) -> None:
        self._decks = decks
        self._cards = cards
        self._collection = collection

    def create(self, player_id: str, name: str, codes: list[str]) -> CreatedDeck:
        """Guarda el deck si pasa todas las comprobaciones."""
        cleaned_name = clean_deck_name(name)
        cleaned_codes = clean_card_codes(codes)
        ids = self._cards.ids_by_code(cleaned_codes)
        owned = self._collection.copies_of(player_id, list(ids.values()))
        # Una carta inexistente recibe el mismo error que una que no posee.
        missing = [code for code in cleaned_codes if ids.get(code) not in owned]
        if missing:
            raise ValidationFailedError(
                f"No posees estas cartas: {', '.join(missing)}.", field="cards"
            )
        stored = self._decks.add(
            player_id,
            cleaned_name,
            deck_name_key(cleaned_name),
            [ids[code] for code in cleaned_codes],
        )
        return CreatedDeck(stored.id, stored.name, cleaned_codes)

    def list_decks(self, player_id: str) -> list[Deck]:
        """Decks del jugador con sus cartas; lista vacía si no tiene."""
        stored = self._decks.list_for(player_id)
        cards = self._cards.summaries(
            {card_id for deck in stored for card_id in deck.card_ids}
        )
        return [self._with_cards(deck, cards) for deck in stored]

    def get_deck(self, player_id: str, deck_id: str) -> Deck:
        """El mismo error si el deck no existe o es de otro jugador (RNF-SEG-04)."""
        stored = self._decks.get_for(deck_id, player_id)
        if stored is None:
            raise NotFoundError("El deck no existe.", field="deck_id")
        return self._with_cards(stored, self._cards.summaries(stored.card_ids))

    @staticmethod
    def _with_cards(deck: StoredDeck, cards: dict[int, CardSummary]) -> Deck:
        return Deck(deck.id, deck.name, [cards[i] for i in deck.card_ids if i in cards])
