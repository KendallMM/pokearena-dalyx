"""Repositorio de ubicaciones sobre MySQL."""

from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.content.locations.models import (
    LocationStatus,
    NewLocation,
    PendingLocation,
    StoredLocation,
)
from app.persistence.relational.database import naive_utc
from app.persistence.relational.models import LocationEffectTypeRow, LocationRow


class SqlLocationRepository:
    """Implementa el puerto LocationRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, location: NewLocation) -> StoredLocation:
        with self._session_factory.begin() as session:
            effect_type_id = None
            if location.effect_type is not None:
                effect_type_id = session.scalars(
                    select(LocationEffectTypeRow.id).where(
                        LocationEffectTypeRow.code == location.effect_type
                    )
                ).one()
            row = LocationRow(
                name=location.name,
                description=location.description,
                card_limit=location.card_limit,
                extra_energy_mode=location.extra_energy_mode.value,
                extra_energy_amount=location.extra_energy_amount,
                effect_type_id=effect_type_id,
                effect_parameters=location.effect_parameters,
                image_id=location.image_id,
                status=location.status.value,
            )
            session.add(row)
            session.flush()
            return StoredLocation(id=row.id, status=LocationStatus(row.status))

    def claim_pending_thumbnails(
        self, now: datetime, limit: int, lease_seconds: int
    ) -> list[PendingLocation]:
        """Reserva ubicaciones pendientes con un UPDATE condicional por cada una: si
        otra instancia ya la tomó, el UPDATE no cambia ninguna fila y se salta."""
        now_utc = naive_utc(now)
        lease_until = now_utc + timedelta(seconds=lease_seconds)
        free = or_(
            LocationRow.thumbnail_claimed_until.is_(None),
            LocationRow.thumbnail_claimed_until <= now_utc,
        )
        pending = LocationStatus.PENDING_THUMBNAIL.value
        claimed: list[PendingLocation] = []
        with self._session_factory.begin() as session:
            candidates = session.execute(
                select(LocationRow.id, LocationRow.image_id)
                .where(LocationRow.status == pending, free)
                .order_by(LocationRow.id)
                .limit(limit)
            ).all()
            for location_id, image_id in candidates:
                result = session.execute(
                    update(LocationRow)
                    .where(
                        LocationRow.id == location_id,
                        LocationRow.status == pending,
                        free,
                    )
                    .values(thumbnail_claimed_until=lease_until)
                )
                if result.rowcount == 1:
                    claimed.append(PendingLocation(id=location_id, image_id=image_id))
        return claimed

    def mark_available(self, location_id: int) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(LocationRow)
                .where(
                    LocationRow.id == location_id,
                    LocationRow.status == LocationStatus.PENDING_THUMBNAIL.value,
                )
                .values(
                    status=LocationStatus.AVAILABLE.value,
                    thumbnail_claimed_until=None,
                    thumbnail_last_error=None,
                )
            )

    def register_thumbnail_failure(
        self, location_id: int, error: str, retry_at: datetime
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(LocationRow)
                .where(LocationRow.id == location_id)
                .values(
                    thumbnail_attempts=LocationRow.thumbnail_attempts + 1,
                    thumbnail_last_error=error[:500],
                    thumbnail_claimed_until=naive_utc(retry_at),
                )
            )
