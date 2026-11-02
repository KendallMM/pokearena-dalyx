"""SqlCardRepository contra la base creada por las migraciones."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound

from app.business.catalog.content.cards.models import CardStatus, NewCard
from app.business.shared.errors import ConflictError
from app.persistence.relational.card_repository import SqlCardRepository
from app.persistence.relational.models import CardRow, CardTypeRow


def _card(card_type="FUE", ability="HAB-000", name="Charmander") -> NewCard:
    return NewCard(
        name=name,
        cost=3,
        power=5,
        card_type=card_type,
        rarity="COMMON",
        ability=ability,
        image_id="abc123",
        status=CardStatus.PENDING_THUMBNAIL,
    )


def test_first_card_of_a_type_gets_001_and_is_pending(session_factory) -> None:
    stored = SqlCardRepository(session_factory).add(_card())
    assert stored.code == "PKA-FUE-001"
    assert stored.status is CardStatus.PENDING_THUMBNAIL
    with session_factory() as session:
        row = session.scalars(select(CardRow)).one()
        assert (row.code, row.status, row.image_id) == (
            "PKA-FUE-001",
            "pending_thumbnail",
            "abc123",
        )
        assert row.created_at is not None


def test_numbers_are_consecutive_per_type(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    codes = [repository.add(_card(t)).code for t in ["FUE", "FUE", "AGU", "FUE", "LUC"]]
    assert codes == [
        "PKA-FUE-001",
        "PKA-FUE-002",
        "PKA-AGU-001",
        "PKA-FUE-003",
        "PKA-LUC-001",
    ]


def test_failed_save_does_not_consume_a_code(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    with pytest.raises(NoResultFound):
        repository.add(_card(ability="HAB-404"))
    assert repository.add(_card()).code == "PKA-FUE-001"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CardRow)) == 1


def test_same_card_content_twice_creates_two_cards(session_factory) -> None:
    """Dos cartas con los mismos datos son cartas distintas; evitar duplicados por
    reintento es trabajo de la idempotencia del gateway."""
    repository = SqlCardRepository(session_factory)
    assert repository.add(_card()).code != repository.add(_card()).code


def test_concurrent_creations_of_the_same_type_get_distinct_codes(
    session_factory,
) -> None:
    repository = SqlCardRepository(session_factory)
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: repository.add(_card()).code, range(24)))
    assert len(set(codes)) == 24
    assert sorted(codes) == [f"PKA-FUE-{n:03d}" for n in range(1, 25)]


def test_type_is_exhausted_after_999_and_rolls_back(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    with session_factory.begin() as session:
        session.execute(
            CardTypeRow.__table__.update()
            .where(CardTypeRow.code == "FUE")
            .values(last_card_number=999)
        )
    with pytest.raises(ConflictError):
        repository.add(_card())
    with session_factory() as session:
        counter = session.scalar(
            select(CardTypeRow.last_card_number).where(CardTypeRow.code == "FUE")
        )
        assert counter == 999  # no se consumió


def test_code_columns_are_wide_enough_for_every_possible_code() -> None:
    """SQLite no aplica el largo de las columnas, MySQL sí: se comprueba aquí."""
    from app.business.catalog.content.cards.card_code import (
        MAX_SEQUENCE,
        build_card_code,
    )
    from app.persistence.relational.models import CardRow

    longest = max(
        len(build_card_code(type_code, MAX_SEQUENCE))
        for type_code in ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"]
    )
    assert longest <= CardRow.code.type.length
