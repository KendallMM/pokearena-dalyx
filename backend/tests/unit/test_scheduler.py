"""Planificador y trabajo de miniaturas."""

import threading

from app.business.automatic_tasks.scheduler import Scheduler
from app.business.automatic_tasks.thumbnail_job import ThumbnailJob
from app.business.catalog.content.cards.models import CreateCard
from tests.unit.image_helpers import make_image


class CountingJob:
    name = "counting"

    def __init__(self) -> None:
        self.runs = 0
        self.ran_twice = threading.Event()

    def run(self) -> None:
        self.runs += 1
        if self.runs >= 2:
            self.ran_twice.set()


class FailingJob:
    name = "failing"

    def run(self) -> None:
        raise RuntimeError("falla")


def test_run_once_runs_every_job() -> None:
    first, second = CountingJob(), CountingJob()
    Scheduler([first, second], 1).run_once()
    assert (first.runs, second.runs) == (1, 1)


def test_a_failing_job_does_not_stop_the_others() -> None:
    working = CountingJob()
    Scheduler([FailingJob(), working], 1).run_once()
    assert working.runs == 1


def test_scheduler_repeats_in_background_and_stops() -> None:
    job = CountingJob()
    scheduler = Scheduler([job], interval_seconds=0.01)
    scheduler.start()
    assert job.ran_twice.wait(timeout=5)
    scheduler.stop()
    runs_after_stop = job.runs
    threading.Event().wait(0.1)
    assert job.runs == runs_after_stop


def test_starting_twice_does_not_create_a_second_thread() -> None:
    scheduler = Scheduler([CountingJob()], interval_seconds=0.01)
    scheduler.start()
    first_thread = scheduler._thread
    scheduler.start()
    assert scheduler._thread is first_thread
    scheduler.stop()


def test_thumbnail_job_asks_cards_to_process_pending(
    card_service, card_repository
) -> None:
    card_service.create_card(
        CreateCard("Charmander", 3, 5, "FUE", "COMMON", "HAB-000", make_image(600, 840))
    )
    ThumbnailJob(card_service).run()
    assert card_repository.rows[1]["status"].value == "available"
