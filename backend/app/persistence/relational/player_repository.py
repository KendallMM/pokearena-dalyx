"""Participante Repositorio de jugadores: mensajes 23–32 del diagrama.

Encapsula las consultas e inserciones en MySQL. La restricción de identidad
estable y la transacción, juntas, resuelven los primeros ingresos simultáneos.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.identity_access.models import ExternalIdentity, Player
from app.business.identity_access.roles import Role
from app.business.shared.errors import NotFoundError, ServiceUnavailableError
from app.business.shared.ports import Transaction
from app.persistence.relational.database import naive_utc
from app.persistence.relational.models import (
    ExternalIdentityRow,
    InitialCollectionDeliveryRow,
    PlayerRow,
)
from app.persistence.relational.transactions import session_of


def to_player(row: PlayerRow) -> Player:
    """Convierte la fila sin exponer el ORM a otras capas."""
    return Player(row.id, row.name, row.email, Role(row.role), row.elo, row.cubes)


class SqlPlayerRepository:
    """La unicidad de la identidad se garantiza en la base de datos."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find_by_identity(self, provider: str, subject: str) -> Player | None:
        """Mensajes 24–26: busca por proveedor/sub y devuelve jugador o ausencia."""
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
            # Mensajes 27–28: cuenta, identidad y solicitud de recompensa se confirman
            # juntas. Si falla cualquier INSERT, se revierte también el jugador.
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
                # Guarda la solicitud pendiente; entregar corresponde a Colección.
                session.add(InitialCollectionDeliveryRow(player_id=row.id))
                session.flush()
                return to_player(row)
        except IntegrityError:
            # Alt, mensajes 29–31: otro ingreso pudo ganar la restricción UNIQUE.
            # La transacción perdedora ya se revirtió; una nueva lectura ve al ganador.
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

    def claim_initial_delivery(
        self,
        transaction: Transaction,
        player_id: str,
        now: datetime,
        cubes: int,
        only_if_due: bool,
    ) -> bool:
        """Marca la entrega como hecha solo si aún está pendiente (pasos 2–5).

        El UPDATE bloquea la fila hasta el COMMIT o ROLLBACK: un ingreso
        simultáneo espera y después ya no encuentra la entrega pendiente.
        """
        now_utc = naive_utc(now)
        conditions = [
            InitialCollectionDeliveryRow.player_id == player_id,
            InitialCollectionDeliveryRow.status == "pending",
        ]
        if only_if_due:
            # Solo el planificador espera; un ingreso del jugador siempre lo intenta.
            conditions.append(InitialCollectionDeliveryRow.next_attempt_at <= now_utc)
        changed = (
            session_of(transaction)
            .execute(
                update(InitialCollectionDeliveryRow)
                .where(*conditions)
                .values(
                    status="delivered",
                    delivered_at=now_utc,
                    cubes_granted=cubes,
                    attempts=InitialCollectionDeliveryRow.attempts + 1,
                )
            )
            .rowcount
        )
        return changed == 1

    def postpone_initial_delivery(self, player_id: str, until: datetime) -> None:
        """Registra un intento fallido y fija cuándo puede reintentar el planificador."""
        try:
            with self._session_factory.begin() as session:
                session.execute(
                    update(InitialCollectionDeliveryRow)
                    .where(
                        InitialCollectionDeliveryRow.player_id == player_id,
                        InitialCollectionDeliveryRow.status == "pending",
                    )
                    .values(
                        attempts=InitialCollectionDeliveryRow.attempts + 1,
                        next_attempt_at=naive_utc(until),
                    )
                )
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudo registrar el intento de entrega."
            ) from exc

    def pending_initial_deliveries(self, now: datetime, limit: int) -> list[str]:
        """Lee solo pendientes vencidos, usando el índice de estado y fecha."""
        try:
            with self._session_factory() as session:
                return list(
                    session.scalars(
                        select(InitialCollectionDeliveryRow.player_id)
                        .where(
                            InitialCollectionDeliveryRow.status == "pending",
                            InitialCollectionDeliveryRow.next_attempt_at
                            <= naive_utc(now),
                        )
                        .order_by(
                            InitialCollectionDeliveryRow.next_attempt_at,
                            InitialCollectionDeliveryRow.id,
                        )
                        .limit(limit)
                    )
                )
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudieron consultar las entregas pendientes."
            ) from exc
