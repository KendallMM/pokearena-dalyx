"""Jugadores en MySQL con creación transaccional y recuperación de carreras."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.identity_access.models import ExternalIdentity, Player
from app.business.identity_access.roles import Role
from app.business.shared.errors import NotFoundError, ServiceUnavailableError
from app.persistence.relational.models import (
    ExternalIdentityRow,
    InitialCollectionDeliveryRow,
    PlayerRow,
)


def to_player(row: PlayerRow) -> Player:
    """Convierte la fila sin exponer el ORM a otras capas."""
    return Player(row.id, row.name, row.email, Role(row.role), row.elo, row.cubes)


class SqlPlayerRepository:
    """La unicidad de la identidad se garantiza en la base de datos."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find_by_identity(self, provider: str, subject: str) -> Player | None:
        """Consulta la identidad externa mediante el índice único compuesto."""
        try:
            with self._session_factory() as session:
                row = session.scalar(
                    select(PlayerRow)
                    .join(ExternalIdentityRow)
                    .where(
                        ExternalIdentityRow.provider == provider,
                        ExternalIdentityRow.subject == subject,
                    )
                )
                return to_player(row) if row is not None else None
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo consultar la cuenta. Reintenta."
            ) from exc

    def create(self, identity: ExternalIdentity) -> Player:
        """Revierte también el jugador perdedor antes de consultar al ganador."""
        try:
            with self._session_factory.begin() as session:
                row = PlayerRow(
                    id=str(uuid4()),
                    name=identity.name,
                    email=identity.email,
                    role=Role.PLAYER.value,
                    elo=0,
                    cubes=0,
                )
                session.add(row)
                session.flush()
                session.add(
                    ExternalIdentityRow(
                        player_id=row.id,
                        provider=identity.provider,
                        subject=identity.subject,
                    )
                )
                session.add(InitialCollectionDeliveryRow(player_id=row.id))
                session.flush()
                return to_player(row)
        except IntegrityError:
            # Nueva sesión/transacción: evita la instantánea anterior de MySQL.
            winner = self.find_by_identity(identity.provider, identity.subject)
            if winner is not None:
                return winner
            raise ServiceUnavailableError(
                "No se pudo crear la cuenta. Reintenta."
            ) from None
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo crear la cuenta. Reintenta."
            ) from exc

    def get(self, player_id: str) -> Player:
        """Lee la cuenta interna, incluidos los cubos ya entregados."""
        try:
            with self._session_factory() as session:
                row = session.get(PlayerRow, player_id)
                if row is None:
                    raise NotFoundError("No se encontró al jugador.")
                return to_player(row)
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo consultar la cuenta. Reintenta."
            ) from exc
