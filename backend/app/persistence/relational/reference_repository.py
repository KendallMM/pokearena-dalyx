"""Repositorio de referencias sobre MySQL."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.references.models import (
    Ability,
    CardType,
    EffectParameter,
    LocationEffectType,
    Rarity,
)
from app.business.shared.errors import ServiceUnavailableError
from app.persistence.relational.models import (
    AbilityRow,
    CardTypeRow,
    LocationEffectTypeRow,
    RarityRow,
)


class SqlReferenceRepository:
    """Implementa el puerto ReferenceRepository. Cada lectura usa su propia sesión."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Sesión de lectura. Si MySQL no responde, lanza un 503 del dominio."""
        try:
            with self._session_factory() as session:
                yield session
        except SQLAlchemyError as exc:
            raise ServiceUnavailableError(
                "No se pudieron consultar las referencias. Reintenta."
            ) from exc

    def list_card_types(self) -> list[CardType]:
        with self._session() as session:
            rows = session.scalars(select(CardTypeRow).order_by(CardTypeRow.id))
            return [CardType(code=row.code, name=row.name) for row in rows]

    def list_rarities(self) -> list[Rarity]:
        with self._session() as session:
            rows = session.scalars(select(RarityRow).order_by(RarityRow.id))
            return [Rarity(code=row.code, name=row.name) for row in rows]

    def list_abilities(self) -> list[Ability]:
        with self._session() as session:
            rows = session.scalars(select(AbilityRow).order_by(AbilityRow.code))
            return [
                Ability(
                    code=row.code,
                    name=row.name,
                    affected_card_type=(
                        row.affected_card_type.code if row.affected_card_type else None
                    ),
                )
                for row in rows
            ]

    def list_location_effect_types(self) -> list[LocationEffectType]:
        with self._session() as session:
            rows = session.scalars(
                select(LocationEffectTypeRow).order_by(LocationEffectTypeRow.id)
            )
            return [
                LocationEffectType(
                    code=row.code,
                    name=row.name,
                    parameters=[
                        EffectParameter(
                            name=p["name"],
                            kind=p["kind"],
                            required=p["required"],
                            minimum=p.get("minimum"),
                            maximum=p.get("maximum"),
                        )
                        for p in row.parameters
                    ],
                )
                for row in rows
            ]
