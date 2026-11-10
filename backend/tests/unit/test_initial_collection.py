"""Colección inicial sin base de datos: reglas y pasos del diagrama de secuencia."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import TypeVar

import pytest

from app.business.catalog.content.cards.card_availability import CardAvailability
from app.business.collection.initial_collection import (
    STARTER_CARD_COUNT,
    STARTER_CUBES,
    DeliveryResult,
    DeliveryStatus,
    InitialCollectionService,
    StarterPack,
)
from app.business.shared.errors import ServiceUnavailableError
from tests.fakes import FakeClock

T = TypeVar("T")


class RecordingRandom:
    """Azar controlado: toma los primeros k y recuerda qué población recibió."""

    def __init__(self) -> None:
        self.populations: list[list[object]] = []

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        self.populations.append(list(population))
        return list(population)[:k]


class FakeTransaction:
    def __init__(self) -> None:
        self.rollback_requested = False

    def rollback(self) -> None:
        self.rollback_requested = True


class World:
    """Dobles de los participantes; anotan cada paso en orden."""

    def __init__(self, commons: int = STARTER_CARD_COUNT + 5) -> None:
        self.steps: list[str] = []
        self.claimable = True
        self.common_ids = list(range(1, commons + 1))
        self.fail_on: str | None = None
        self.only_if_due: list[bool] = []

    def _step(self, name: str) -> None:
        self.steps.append(name)
        if self.fail_on == name:
            raise ServiceUnavailableError("storage unavailable")

    # TransactionManager
    @contextmanager
    def begin(self) -> Iterator[FakeTransaction]:
        transaction = FakeTransaction()
        try:
            yield transaction
        except ServiceUnavailableError:
            self.steps.append("rollback")
            raise
        self.steps.append("rollback" if transaction.rollback_requested else "commit")

    # Repositorio de jugadores
    def claim_initial_delivery(self, transaction, player_id, now, cubes, only_if_due):
        self.only_if_due.append(only_if_due)
        self._step("claim")
        assert cubes == STARTER_CUBES
        return self.claimable

    def postpone_initial_delivery(self, player_id: str, until: datetime) -> None:
        self.steps.append("postpone")

    def pending_initial_deliveries(self, now: datetime, limit: int) -> list[str]:
        return ["p1", "p2"]

    # Repositorio de cartas
    def available_ids_by_rarity(self, transaction, rarity_code: str) -> list[int]:
        assert rarity_code == "COMMON"
        self._step("cards")
        return self.common_ids

    # Repositorio de colección
    def add_cards(self, transaction, player_id: str, card_ids: list[int]) -> None:
        self._step("collection")
        assert len(card_ids) == STARTER_CARD_COUNT == len(set(card_ids))

    # Repositorio de cubos
    def credit(self, transaction, player_id, amount, reason, reference) -> int:
        self._step("cubes")
        assert (amount, reason, reference) == (
            STARTER_CUBES,
            "initial_collection",
            player_id,
        )
        return amount


def service_for(world: World, random: RecordingRandom | None = None):
    return InitialCollectionService(
        transactions=world,
        deliveries=world,
        cards=CardAvailability(world),
        collection=world,
        cubes=world,
        clock=FakeClock(),
        random=random or RecordingRandom(),
    )


def test_starter_pack_rules_match_the_user_story() -> None:
    pack = StarterPack(RecordingRandom())
    assert (pack.card_count, pack.cubes, pack.rarity_code) == (15, 1_000, "COMMON")


def test_fewer_candidates_than_required_gives_nothing() -> None:
    random = RecordingRandom()
    pack = StarterPack(random)
    assert pack.choose_cards(list(range(STARTER_CARD_COUNT - 1))) is None
    assert random.populations == []


def test_duplicate_candidates_do_not_count_twice() -> None:
    pack = StarterPack(RecordingRandom())
    almost = list(range(STARTER_CARD_COUNT - 1))
    assert pack.choose_cards(almost + almost) is None


def test_cards_are_distinct_and_chosen_by_the_server_random() -> None:
    random = RecordingRandom()
    pack = StarterPack(random)
    candidates = [30, 10, 20, *range(100, 120)]
    chosen = pack.choose_cards(candidates)
    assert chosen is not None
    assert len(chosen) == STARTER_CARD_COUNT == len(set(chosen))
    assert set(chosen) <= set(candidates)
    # La población llega ordenada: el resultado solo depende del azar inyectado,
    # no del orden en que la base devolvió las filas.
    assert random.populations == [sorted(candidates)]


def test_successful_delivery_follows_the_diagram_and_commits() -> None:
    world = World()
    result = service_for(world).deliver("p0")
    assert result.status is DeliveryStatus.DELIVERED
    assert world.steps == ["claim", "cards", "collection", "cubes", "commit"]


def test_already_delivered_rolls_back_without_touching_anything() -> None:
    world = World()
    world.claimable = False
    result = service_for(world).deliver("p0")
    assert result.status is DeliveryStatus.ALREADY_DELIVERED
    assert world.steps == ["claim", "rollback"]


def test_not_enough_commons_rolls_back_and_stays_pending() -> None:
    world = World(commons=STARTER_CARD_COUNT - 1)
    result = service_for(world).deliver("p0")
    assert result.status is DeliveryStatus.UNAVAILABLE
    assert "aún no está disponible" in result.message
    # Deshace la marca; el intento se anota aparte para el planificador.
    assert world.steps == ["claim", "cards", "rollback", "postpone"]


@pytest.mark.parametrize("failing_step", ["claim", "cards", "collection", "cubes"])
def test_any_failing_step_rolls_back_everything(failing_step: str) -> None:
    world = World()
    world.fail_on = failing_step
    result = service_for(world).deliver("p0")
    assert result.status is DeliveryStatus.PENDING
    assert "próximo ingreso" in result.message
    assert "commit" not in world.steps
    assert world.steps[-2:] == ["rollback", "postpone"]


def test_login_always_tries_and_scheduler_respects_the_wait() -> None:
    world = World()
    service = service_for(world)
    service.deliver("p0")
    service.run()
    assert world.only_if_due == [False, True, True]


def test_delivered_message_mentions_the_rewards() -> None:
    message = DeliveryResult.of(DeliveryStatus.DELIVERED).message
    assert str(STARTER_CARD_COUNT) in message and "1,000" in message
