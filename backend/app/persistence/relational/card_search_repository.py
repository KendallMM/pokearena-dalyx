"""Consulta de cartas para la búsqueda, sobre MySQL."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from app.business.catalog.content.cards.models import CardStatus
from app.business.catalog.references.models import Ability, CardType, Rarity
from app.business.catalog.search.models import CardCriteria, CardSummary
from app.persistence.relational.models import (
    AbilityRow,
    CardRow,
    CardTypeRow,
    RarityRow,
)


def _escape_like(text: str) -> str:
    """Para que % y _ del texto buscado se tomen como letras y no como comodines."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlCardSearchRepository:
    """Implementa el puerto CardSearchRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def search(
        self, criteria: CardCriteria, after_id: int, limit: int
    ) -> list[CardSummary]:
        affected = aliased(CardTypeRow)
        statement = (
            select(CardRow, CardTypeRow, RarityRow, AbilityRow, affected.code)
            .join(CardTypeRow, CardRow.card_type_id == CardTypeRow.id)
            .join(RarityRow, CardRow.rarity_id == RarityRow.id)
            .join(AbilityRow, CardRow.ability_id == AbilityRow.id)
            .outerjoin(affected, AbilityRow.affected_card_type_id == affected.id)
            # Paginación por cursor: estable aunque se creen cartas durante el recorrido.
            .where(CardRow.id > after_id)
            .order_by(CardRow.id)
            .limit(limit)
        )
        # Cada criterio activo se suma con AND: el resultado cumple todos a la vez.
        if criteria.code:
            statement = statement.where(CardRow.code == criteria.code)
        if criteria.search_name:
            pattern = f"%{_escape_like(criteria.search_name)}%"
            statement = statement.where(CardRow.search_name.like(pattern, escape="\\"))
        if criteria.cost_min is not None:
            statement = statement.where(CardRow.cost >= criteria.cost_min)
        if criteria.cost_max is not None:
            statement = statement.where(CardRow.cost <= criteria.cost_max)
        if criteria.power_min is not None:
            statement = statement.where(CardRow.power >= criteria.power_min)
        if criteria.power_max is not None:
            statement = statement.where(CardRow.power <= criteria.power_max)
        if criteria.card_type:
            statement = statement.where(CardTypeRow.code == criteria.card_type)
        if criteria.rarity:
            statement = statement.where(RarityRow.code == criteria.rarity)
        if criteria.ability:
            statement = statement.where(AbilityRow.code == criteria.ability)

        with self._session_factory() as session:
            return [
                CardSummary(
                    id=card.id,
                    code=card.code,
                    name=card.name,
                    cost=card.cost,
                    power=card.power,
                    card_type=CardType(code=card_type.code, name=card_type.name),
                    rarity=Rarity(code=rarity.code, name=rarity.name),
                    ability=Ability(
                        code=ability.code,
                        name=ability.name,
                        affected_card_type=affected_code,
                    ),
                    status=CardStatus(card.status),
                    thumbnail_attempts=card.thumbnail_attempts,
                )
                for card, card_type, rarity, ability, affected_code in session.execute(
                    statement
                )
            ]

    def find_image_id(self, code: str) -> str | None:
        with self._session_factory() as session:
            return session.scalars(
                select(CardRow.image_id).where(CardRow.code == code)
            ).first()
