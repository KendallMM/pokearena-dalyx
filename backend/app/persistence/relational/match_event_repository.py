"""Registro relacional de eventos pendientes de copiar al historial."""

from uuid import uuid4

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.automatic_tasks.match_events_job import PendingMatchEvent
from app.business.shared.errors import ServiceUnavailableError
from app.business.shared.ports import Transaction
from app.persistence.relational.matchmaking_models import pending_match_events
from app.persistence.relational.transactions import session_of


class SqlMatchEventRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def add(self, tx: Transaction, match_id: str, state: dict) -> None:
        session_of(tx).execute(
            insert(pending_match_events).values(
                id=str(uuid4()),
                match_id=match_id,
                payload={
                    "type": "match_started",
                    "state": state,
                },
            )
        )

    def next_pending(self, after: PendingMatchEvent | None) -> PendingMatchEvent | None:
        events = pending_match_events.c
        query = (
            select(events.id, events.match_id, events.payload, events.created_at)
            .where(events.copied.is_(False))
            .order_by(events.created_at, events.id)
            .limit(1)
        )
        if after is not None:
            query = query.where(
                or_(
                    events.created_at > after.created_at,
                    and_(events.created_at == after.created_at, events.id > after.id),
                )
            )
        with self.sessions() as session:
            row = session.execute(query).one_or_none()
            return PendingMatchEvent(*row) if row is not None else None

    def mark_copied(self, event_id: str) -> None:
        try:
            with self.sessions.begin() as session:
                session.execute(
                    update(pending_match_events)
                    .where(
                        pending_match_events.c.id == event_id,
                        pending_match_events.c.copied.is_(False),
                    )
                    .values(copied=True)
                )
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo confirmar la copia del evento."
            ) from exc
