"""Consultas y transiciones condicionales de la fila en MySQL."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.matchmaking.elo_queue import Search
from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Transaction
from app.persistence.relational.database import naive_utc
from app.persistence.relational.matchmaking_models import (
    match_search_operations,
    match_searches,
)
from app.persistence.relational.transactions import session_of

columns = match_searches.c


def read_search(row) -> Search:
    values = dict(row)
    del values["open_player_id"]
    values["created_at"] = values["created_at"].replace(tzinfo=timezone.utc)
    values["last_seen_at"] = values["last_seen_at"].replace(tzinfo=timezone.utc)
    return Search(**values)


class SqlSearchRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def open_for_player(
        self, tx: Transaction, player_id: str
    ) -> tuple[str, str] | None:
        row = (
            session_of(tx)
            .execute(
                select(columns.id, columns.status).where(
                    columns.open_player_id == player_id
                )
            )
            .one_or_none()
        )
        return (row.id, row.status) if row else None

    def operation(
        self, tx: Transaction, player_id: str, key_hash: str
    ) -> Search | None:
        session = session_of(tx)
        row = (
            session.execute(
                select(match_searches)
                .join(
                    match_search_operations,
                    match_search_operations.c.search_id == columns.id,
                )
                .where(
                    columns.player_id == player_id,
                    match_search_operations.c.player_id == player_id,
                    match_search_operations.c.key_hash == key_hash,
                )
            )
            .mappings()
            .one_or_none()
        )
        return read_search(row) if row else None

    def record_operation(self, tx: Transaction, search: Search, key_hash: str) -> None:
        session_of(tx).execute(
            insert(match_search_operations).values(
                player_id=search.player_id, search_id=search.id, key_hash=key_hash
            )
        )

    def add(self, tx: Transaction, search: Search) -> Search:
        """Inserta la búsqueda o recupera la abierta si el índice único la rechaza."""
        session = session_of(tx)
        values = asdict(search)
        values["created_at"] = naive_utc(search.created_at)
        values["last_seen_at"] = naive_utc(search.last_seen_at or search.created_at)
        try:
            with session.begin_nested():
                session.execute(insert(match_searches).values(**values))
        except IntegrityError as error:
            reason = str(error.orig).lower()
            if (
                "uq_search_open_player" not in reason
                and "match_searches.open_player_id" not in reason
            ):
                raise
            current = (
                session.execute(
                    select(match_searches)
                    .where(columns.open_player_id == search.player_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise
            return read_search(current)
        return search

    def consult(
        self, tx: Transaction, player_id: str, now: datetime, cutoff: datetime
    ) -> Search | None:
        session = session_of(tx)
        session.execute(
            update(match_searches)
            .where(
                columns.player_id == player_id,
                columns.status == "waiting",
                columns.last_seen_at >= naive_utc(cutoff),
            )
            .values(last_seen_at=naive_utc(now))
        )
        row = (
            session.execute(
                select(match_searches)
                .where(columns.player_id == player_id)
                .order_by(columns.created_at.desc(), columns.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return read_search(row) if row else None

    def in_transaction(
        self, tx: Transaction, player_id: str, search_id: str
    ) -> Search | None:
        return self._get(session_of(tx), player_id, search_id, lock=True)

    def expire(self, tx: Transaction, cutoff: datetime) -> int:
        return (
            session_of(tx)
            .execute(
                update(match_searches)
                .where(
                    columns.status == "waiting",
                    columns.last_seen_at < naive_utc(cutoff),
                )
                .values(status="expired", error=None)
            )
            .rowcount
        )

    def cancel_waiting(
        self, tx: Transaction, player_id: str, search_id: str
    ) -> Search | None:
        session = session_of(tx)
        changed = session.execute(
            update(match_searches)
            .where(
                columns.id == search_id,
                columns.player_id == player_id,
                columns.status == "waiting",
            )
            .values(status="cancelled", error=None)
        ).rowcount
        if not changed:
            return None
        # MySQL no devuelve la fila en UPDATE. La escritura la mantiene bloqueada
        # mientras se recuperan los datos de la respuesta.
        result = self._get(session, player_id, search_id, lock=False)
        if result is None:
            raise ServiceUnavailableError("No se pudo recuperar la búsqueda cancelada.")
        return result

    def count_abandoned(
        self, tx: Transaction, ids: tuple[str, str], cutoff: datetime
    ) -> int:
        return session_of(tx).scalar(
            select(func.count())
            .select_from(match_searches)
            .where(columns.id.in_(ids), columns.last_seen_at < naive_utc(cutoff))
        )

    def reserve_bot(self, tx: Transaction, search_id: str, cutoff: datetime) -> int:
        return (
            session_of(tx)
            .execute(
                update(match_searches)
                .where(
                    columns.id == search_id,
                    columns.status == "waiting",
                    columns.last_seen_at >= naive_utc(cutoff),
                )
                .values(status="bot")
            )
            .rowcount
        )

    def found_bot(self, tx: Transaction, search_id: str, match_id: str) -> int:
        return (
            session_of(tx)
            .execute(
                update(match_searches)
                .where(columns.id == search_id, columns.status == "bot")
                .values(status="found", match_id=match_id, error=None)
            )
            .rowcount
        )

    def get(self, player_id: str, search_id: str) -> Search | None:
        with self._read_session() as session:
            return self._get(session, player_id, search_id)

    @staticmethod
    def _get(
        session: Session, player_id: str, search_id: str, *, lock: bool = False
    ) -> Search | None:
        query = select(match_searches).where(
            columns.player_id == player_id, columns.id == search_id
        )
        row = (
            session.execute(query.with_for_update() if lock else query)
            .mappings()
            .one_or_none()
        )
        return read_search(row) if row else None

    def waiting(self, cutoff: datetime | None = None) -> list[Search]:
        """Lee las búsquedas clasificatorias pendientes, de la más antigua a la más nueva."""
        with self._read_session() as session:
            query = select(match_searches).where(
                columns.status == "waiting", columns.mode == "ranked"
            )
            if cutoff is not None:
                query = query.where(columns.last_seen_at >= naive_utc(cutoff))
            rows = session.execute(
                query.order_by(columns.created_at, columns.id)
            ).mappings()
            return [read_search(row) for row in rows]

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        try:
            with self.sessions() as session:
                yield session
        except SQLAlchemyError as error:
            raise ServiceUnavailableError(
                "No se pudieron consultar las búsquedas. Reintenta."
            ) from error

    def reserve(self, tx: Transaction, ids: tuple[str, str]) -> int:
        """Reserva las filas que siguen en espera y devuelve cuántas cambió."""
        return (
            session_of(tx)
            .execute(
                update(match_searches)
                .where(columns.id.in_(ids), columns.status == "waiting")
                .values(status="reserved")
            )
            .rowcount
        )

    def found(self, tx: Transaction, ids: tuple[str, str], match_id: str) -> int:
        """Marca como encontradas las filas reservadas y les asigna la partida."""
        return (
            session_of(tx)
            .execute(
                update(match_searches)
                .where(columns.id.in_(ids), columns.status == "reserved")
                .values(status="found", match_id=match_id, error=None)
            )
            .rowcount
        )

    def record_failure(self, ids: tuple[str, str], message: str) -> None:
        """Registra la causa en las búsquedas que aún esperan rival."""
        with self.sessions.begin() as session:
            session.execute(
                update(match_searches)
                .where(columns.id.in_(ids), columns.status == "waiting")
                .values(error=message)
            )
