"""Repositorio de mazos sobre MySQL."""

from contextlib import nullcontext
from uuid import uuid4

from app.business.shared.ports import Transaction
from app.persistence.relational.transactions import session_of

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.collection.decks import DeckNameConflictError, StoredDeck
from app.business.shared.errors import ServiceUnavailableError
from app.persistence.relational.models import DeckCardRow, DeckRow


class SqlDeckRepository:
    """Implementa el puerto DeckRepository. Toda lectura filtra por jugador."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(
        self, player_id: str, name: str, name_key: str, card_ids: list[int]
    ) -> StoredDeck:
        """El UNIQUE resuelve dos creaciones simultáneas con el mismo nombre."""
        deck_id = str(uuid4())
        try:
            with self._session_factory.begin() as session:
                session.add(
                    DeckRow(
                        id=deck_id, player_id=player_id, name=name, name_key=name_key
                    )
                )
                session.flush()
                session.add_all(
                    [DeckCardRow(deck_id=deck_id, card_id=i) for i in card_ids]
                )
        except IntegrityError as exc:
            if self._name_exists(player_id, name_key):
                raise DeckNameConflictError(name) from None
            raise ServiceUnavailableError(
                "No se pudo guardar el deck. Reintenta."
            ) from exc
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar el deck. Reintenta."
            ) from exc
        return StoredDeck(deck_id, name, sorted(card_ids))

    def _name_exists(self, player_id: str, name_key: str) -> bool:
        try:
            with self._session_factory() as session:
                return (
                    session.scalar(
                        select(DeckRow.id).where(
                            DeckRow.player_id == player_id,
                            DeckRow.name_key == name_key,
                        )
                    )
                    is not None
                )
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar el deck. Reintenta."
            ) from exc

    def list_for(self, player_id: str) -> list[StoredDeck]:
        return self._read(DeckRow.player_id == player_id)

    def get_for(
        self, deck_id: str, player_id: str, *, tx: Transaction | None = None
    ) -> StoredDeck | None:
        found = self._read(DeckRow.id == deck_id, DeckRow.player_id == player_id, tx=tx)
        return found[0] if found else None

    def _read(self, *conditions, tx: Transaction | None = None) -> list[StoredDeck]:
        statement = (
            select(DeckRow.id, DeckRow.name, DeckCardRow.card_id)
            .outerjoin(DeckCardRow, DeckCardRow.deck_id == DeckRow.id)
            .where(*conditions)
            .order_by(DeckRow.created_at, DeckRow.id, DeckCardRow.card_id)
        )
        decks: dict[str, StoredDeck] = {}
        try:
            context = nullcontext(session_of(tx)) if tx else self._session_factory()
            with context as session:
                for deck_id, name, card_id in session.execute(statement):
                    deck = decks.setdefault(deck_id, StoredDeck(deck_id, name, []))
                    if card_id is not None:
                        deck.card_ids.append(card_id)
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudieron consultar los decks. Reintenta."
            ) from exc
        return list(decks.values())
