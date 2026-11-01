"""Repositorio de referencias sobre MySQL."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.business.catalog.references.models import Ability, CardType, Rarity
from app.persistence.relational.models import AbilityRow, CardTypeRow, RarityRow


class SqlReferenceRepository:
    """Implementa el puerto ReferenceRepository. Cada lectura usa su propia sesión."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_card_types(self) -> list[CardType]:
        with self._session_factory() as session:
            rows = session.scalars(select(CardTypeRow).order_by(CardTypeRow.id))
            return [CardType(code=row.code, name=row.name) for row in rows]

    def list_rarities(self) -> list[Rarity]:
        with self._session_factory() as session:
            rows = session.scalars(select(RarityRow).order_by(RarityRow.id))
            return [Rarity(code=row.code, name=row.name) for row in rows]

    def list_abilities(self) -> list[Ability]:
        with self._session_factory() as session:
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
