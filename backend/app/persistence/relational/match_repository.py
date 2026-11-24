"""Persistencia de partidas y participantes."""

from sqlalchemy import insert, select
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

    def active(self, player_id: str, tx: Transaction | None = None) -> str | None:
        query = select(match_players.c.match_id).where(
            match_players.c.active_player_id == player_id
        )
        if tx is not None:
            return session_of(tx).scalar(query)
        with self.sessions() as session:
            return session.scalar(query)

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
