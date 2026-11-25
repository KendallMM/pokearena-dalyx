"""Presupuesto de ejecución del historial sin bloquear otros trabajos."""

from unittest.mock import Mock

from app.business.automatic_tasks.match_events_job import MatchEventsJob
from app.business.shared.errors import ServiceUnavailableError


def test_document_outage_leaves_event_pending_and_yields_shared_thread(monkeypatch):
    pending, history = Mock(), Mock()
    event = pending.next_pending.return_value
    history.store.side_effect = ServiceUnavailableError("MongoDB no disponible.")
    ticks = iter((0.0, 0.0, 1.0, 5.0))
    monkeypatch.setattr(
        "app.business.automatic_tasks.match_events_job.monotonic",
        lambda: next(ticks),
    )

    MatchEventsJob(pending, history, 5).run()

    pending.next_pending.assert_called_once_with(None)
    history.store.assert_called_once_with(event, 4)
    pending.mark_copied.assert_not_called()
