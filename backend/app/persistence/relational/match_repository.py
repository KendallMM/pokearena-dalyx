"""Persistencia de partidas y participantes."""

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.business.game.matches import MatchEntry
from app.business.shared.ports import Transaction
from app.persistence.relational.matchmaking_models import (
    match_players,
    matches,
)
from app.persistence.relational.transactions import session_of


class SqlMatchRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def initial_state_for(self, match_id: str, player_id: str) -> dict | None:
        query = (
            select(matches.c.initial_state)
            .join(match_players, matches.c.id == match_players.c.match_id)
            .where(matches.c.id == match_id, match_players.c.player_id == player_id)
        )
        with self.sessions() as session:
            return session.scalar(query)

    def active(self, player_id: str, tx: Transaction | None = None) -> str | None:
        query = select(match_players.c.match_id).where(
            match_players.c.active_player_id == player_id
        )
        if tx is not None:
            return session_of(tx).scalar(query)
        with self.sessions() as session:
            return session.scalar(query)

    def save_initial_state(self, tx: Transaction, match_id: str, state: dict) -> None:
        changed = session_of(tx).execute(
            update(matches).where(matches.c.id == match_id).values(initial_state=state)
        )
        if changed.rowcount != 1:
            raise RuntimeError("No se pudo guardar el estado inicial de la partida.")

    def add_bot(
        self, tx: Transaction, match_id: str, entry: MatchEntry, bot_cards: list[int]
    ) -> None:
        session = session_of(tx)
        session.execute(
            insert(matches).values(id=match_id, mode="bot", bot_card_ids=bot_cards)
        )
        session.execute(
            insert(match_players).values(
                match_id=match_id,
                player_id=entry.player_id,
                deck_id=entry.deck_id,
                card_ids=entry.card_ids,
            )
        )

    def add(
        self,
        tx: Transaction,
        match_id: str,
        mode: str,
        entries: tuple[MatchEntry, MatchEntry],
    ) -> None:
        session = session_of(tx)
        ordered = sorted(entries, key=lambda entry: entry.player_id)
        session.execute(insert(matches).values(id=match_id, mode=mode))
        session.execute(
            insert(match_players),
            [
                {
                    "match_id": match_id,
                    "player_id": entry.player_id,
                    "deck_id": entry.deck_id,
                    "card_ids": entry.card_ids,
                }
                for entry in ordered
            ],
        )
