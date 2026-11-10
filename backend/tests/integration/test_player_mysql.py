"""Garantías de concurrencia verificadas contra MySQL 8.4, sin SQLite."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.business.identity_access.models import ExternalIdentity, Player
from app.business.collection.initial_collection import (
    STARTER_CARD_COUNT,
    STARTER_CUBES,
    DeliveryResult,
    DeliveryStatus,
)
from app.persistence.relational.database import build_session_factory
from app.persistence.relational.models import (
    CardRow,
    CubeMovementRow,
    ExternalIdentityRow,
    InitialCollectionDeliveryRow,
    PlayerCardRow,
    PlayerRow,
)
from app.persistence.relational.player_repository import SqlPlayerRepository
from tests.builders import real_initial_collection_service
from tests.integration.conftest import alembic_config


@pytest.fixture(scope="module")
def mysql_sessions() -> sessionmaker[Session]:
    """Usa únicamente la base aislada que configura docker-compose.test.yml."""
    url = os.environ.get("TEST_MYSQL_URL")
    if not url:
        pytest.skip("MySQL externo no configurado: ejecutar docker-compose.test.yml")
    command.upgrade(alembic_config(url), "head")
    return build_session_factory(url)


def test_mysql_concurrent_account_creation_and_collection(
    mysql_sessions: sessionmaker[Session],
) -> None:
    """Fuerza dos INSERT de la misma identidad y dos entregas simultáneas."""
    repository = SqlPlayerRepository(mysql_sessions)
    identity = ExternalIdentity("google", str(uuid4()), "test@example.test", "Jugador")
    barrier = Barrier(2)

    def create_account(_index: int) -> Player:
        assert repository.find_by_identity(identity.provider, identity.subject) is None
        barrier.wait(timeout=10)
        return repository.create(identity)

    with ThreadPoolExecutor(max_workers=2) as pool:
        accounts = list(pool.map(create_account, range(2)))
    assert accounts[0].id == accounts[1].id
    assert accounts[0].elo == 0
    assert accounts[0].role.value == "player"
    player_id = accounts[0].id
    batch = uuid4().hex[:6]
    with mysql_sessions.begin() as session:
        # rarity_id=1 es COMMON en el catálogo de referencia migrado.
        session.add_all(
            [
                CardRow(
                    code=f"T{batch}{index:02}",
                    name="Carta de prueba",
                    search_name="carta de prueba",
                    cost=1,
                    power=1,
                    card_type_id=1,
                    rarity_id=1,
                    ability_id=1,
                    image_id=str(uuid4()),
                    status="available",
                )
                for index in range(STARTER_CARD_COUNT)
            ]
        )
    collections = real_initial_collection_service(mysql_sessions)
    grant_barrier = Barrier(2)

    def grant(_index: int) -> DeliveryResult:
        grant_barrier.wait(timeout=10)
        return collections.deliver(player_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(grant, range(2)))
    assert {result.status for result in results} == {
        DeliveryStatus.DELIVERED,
        DeliveryStatus.ALREADY_DELIVERED,
    }
    with mysql_sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ExternalIdentityRow)
                .where(ExternalIdentityRow.subject == identity.subject)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(InitialCollectionDeliveryRow)
                .where(InitialCollectionDeliveryRow.player_id == player_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.sum(PlayerCardRow.quantity)).where(
                    PlayerCardRow.player_id == player_id
                )
            )
            == STARTER_CARD_COUNT
        )
        assert session.get(PlayerRow, player_id).cubes == STARTER_CUBES
        assert (
            session.scalar(
                select(func.count())
                .select_from(CubeMovementRow)
                .where(CubeMovementRow.player_id == player_id)
            )
            == 1
        )
        assert (
            session.scalar(
                text(
                    "SELECT COUNT(*) FROM players p LEFT JOIN external_identities e ON e.player_id = p.id WHERE e.id IS NULL"
                )
            )
            == 0
        )


def test_mysql_provider_subject_is_case_sensitive(
    mysql_sessions: sessionmaker[Session],
) -> None:
    """La colación por defecto de MySQL no debe fusionar identidades distintas."""
    repository = SqlPlayerRepository(mysql_sessions)
    subject = str(uuid4())
    lower = repository.create(
        ExternalIdentity("google", f"a-{subject}", "same@example.test", "A")
    )
    upper = repository.create(
        ExternalIdentity("google", f"A-{subject}", "same@example.test", "A")
    )
    assert lower.id != upper.id
    assert repository.find_by_identity("google", f"a-{subject}").id == lower.id
