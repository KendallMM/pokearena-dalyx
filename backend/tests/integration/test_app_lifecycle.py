"""El planificador arranca con la aplicación y se detiene al apagarla."""

import threading

from fastapi.testclient import TestClient

from app.business.automatic_tasks.scheduler import Scheduler
from app.business.catalog.references.reference_service import ReferenceService
from app.composition import Container
from app.main import create_app


class SignalJob:
    name = "signal"

    def __init__(self) -> None:
        self.runs = 0
        self.started = threading.Event()

    def run(self) -> None:
        self.runs += 1
        self.started.set()


def _container(settings, validator, store, reference_repository, card_service, job):
    return Container(
        settings,
        validator,
        store,
        ReferenceService(reference_repository),
        card_service,
        scheduler=Scheduler([job], interval_seconds=0.01),
    )


def test_scheduler_runs_while_the_app_is_up_and_stops_on_shutdown(
    settings, validator, store, reference_repository, card_service
) -> None:
    job = SignalJob()
    app = create_app(
        _container(settings, validator, store, reference_repository, card_service, job)
    )
    with TestClient(app) as client:
        assert job.started.wait(timeout=5)
        assert (
            client.get("/health").status_code == 200
        )  # la API responde mientras tanto
    runs_at_shutdown = job.runs
    threading.Event().wait(0.1)
    assert job.runs == runs_at_shutdown


def test_app_without_scheduler_starts_normally(
    settings, validator, store, reference_repository, card_service
) -> None:
    container = Container(
        settings, validator, store, ReferenceService(reference_repository), card_service
    )
    with TestClient(create_app(container)) as client:
        assert client.get("/health").status_code == 200
