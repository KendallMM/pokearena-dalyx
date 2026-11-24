"""Planificador: ejecuta los trabajos en segundo plano cada cierto tiempo."""

import logging
import threading
from collections.abc import Mapping
from time import monotonic
from typing import Protocol

logger = logging.getLogger(__name__)


class Job(Protocol):
    """Trabajo en segundo plano."""

    name: str

    def run(self) -> None:
        """Ejecuta una pasada del trabajo."""
        ...


class Scheduler:
    """Corre los trabajos en un hilo propio, fuera del manejo de solicitudes.

    Un error en un trabajo se registra y no detiene al planificador ni a los demás.
    Si hay varias instancias de la API, cada una tiene su planificador; cada trabajo
    debe evitar que dos instancias procesen lo mismo (ver ADR de tareas automáticas).
    """

    def __init__(
        self,
        jobs: list[Job],
        interval_seconds: float,
        *,
        job_intervals: Mapping[str, float] | None = None,
    ) -> None:
        self._jobs = jobs
        self._interval_seconds = interval_seconds
        self._job_intervals = dict(job_intervals or {})
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> None:
        """Ejecuta cada trabajo una vez."""
        for job in self._jobs:
            self._run_job(job)

    @staticmethod
    def _run_job(job: Job) -> None:
        try:
            job.run()
        except Exception:
            logger.error("Falló el trabajo %s", job.name, exc_info=True)

    def start(self) -> None:
        """Arranca el hilo. Llamarlo dos veces no crea un segundo hilo."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="scheduler", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 10) -> None:
        """Pide que termine y espera a que acabe la pasada en curso."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        if not self._job_intervals:
            while not self._stop.is_set():
                self.run_once()
                self._stop.wait(self._interval_seconds)
            return

        deadlines = [monotonic()] * len(self._jobs)
        while not self._stop.is_set():
            for index, job in enumerate(self._jobs):
                now = monotonic()
                if now >= deadlines[index]:
                    interval = self._job_intervals.get(job.name, self._interval_seconds)
                    deadlines[index] = now + interval
                    self._run_job(job)
            next_run = min(deadlines, default=monotonic() + self._interval_seconds)
            self._stop.wait(max(0, next_run - monotonic()))
