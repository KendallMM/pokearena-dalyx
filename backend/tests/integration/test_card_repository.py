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
        search_name=name.lower(),
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


# ---- reserva y seguimiento de miniaturas ----
from datetime import datetime, timedelta, timezone  # noqa: E402

NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def _row(session_factory, code):
    with session_factory() as session:
        return session.scalars(select(CardRow).where(CardRow.code == code)).one()


def test_claim_returns_pending_cards_in_order_up_to_the_limit(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    for _ in range(3):
        repository.add(_card())
    claimed = repository.claim_pending_thumbnails(NOW, limit=2, lease_seconds=120)
    assert [c.code for c in claimed] == ["PKA-FUE-001", "PKA-FUE-002"]
    assert all(c.image_id == "abc123" for c in claimed)


def test_claimed_cards_are_not_claimed_again_until_the_lease_expires(
    session_factory,
) -> None:
    repository = SqlCardRepository(session_factory)
    repository.add(_card())
    assert len(repository.claim_pending_thumbnails(NOW, 10, 120)) == 1
    assert (
        repository.claim_pending_thumbnails(NOW + timedelta(seconds=60), 10, 120) == []
    )
    assert (
        len(repository.claim_pending_thumbnails(NOW + timedelta(seconds=121), 10, 120))
        == 1
    )


def test_mark_available_changes_status_and_clears_the_reservation(
    session_factory,
) -> None:
    repository = SqlCardRepository(session_factory)
    repository.add(_card())
    card = repository.claim_pending_thumbnails(NOW, 10, 120)[0]
    repository.mark_available(card.id)
    row = _row(session_factory, "PKA-FUE-001")
    assert row.status == "available"
    assert row.thumbnail_claimed_until is None
    assert repository.claim_pending_thumbnails(NOW + timedelta(hours=1), 10, 120) == []


def test_failure_keeps_the_card_pending_and_records_the_error(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    repository.add(_card())
    card = repository.claim_pending_thumbnails(NOW, 10, 120)[0]
    retry_at = NOW + timedelta(seconds=60)
    repository.register_thumbnail_failure(card.id, "MongoDB no responde", retry_at)
    row = _row(session_factory, "PKA-FUE-001")
    assert row.status == "pending_thumbnail"
    assert row.thumbnail_attempts == 1
    assert row.thumbnail_last_error == "MongoDB no responde"
    assert (
        repository.claim_pending_thumbnails(NOW + timedelta(seconds=30), 10, 120) == []
    )
    assert len(repository.claim_pending_thumbnails(retry_at, 10, 120)) == 1


def test_long_errors_are_truncated_to_the_column_size(session_factory) -> None:
    repository = SqlCardRepository(session_factory)
    repository.add(_card())
    card = repository.claim_pending_thumbnails(NOW, 10, 120)[0]
    repository.register_thumbnail_failure(card.id, "x" * 900, NOW)
    assert len(_row(session_factory, "PKA-FUE-001").thumbnail_last_error) == 500


def test_two_instances_claiming_at_once_never_take_the_same_card(
    session_factory,
) -> None:
    repository = SqlCardRepository(session_factory)
    for _ in range(12):
        repository.add(_card())

    codes: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        # Varias pasadas, cada una con 6 instancias reservando a la vez. Las que pierden
        # una carrera la dejan para la siguiente pasada.
        for _ in range(10):
            batches = list(
                pool.map(
                    lambda _: repository.claim_pending_thumbnails(NOW, 4, 120), range(6)
                )
            )
            claimed = [card.code for batch in batches for card in batch]
            if not claimed:
                break
            codes.extend(claimed)

    assert len(codes) == len(set(codes))  # ninguna carta se reservó dos veces
    assert len(codes) == 12  # y ninguna se perdió
