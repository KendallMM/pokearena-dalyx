"""Planificador: ejecuta los trabajos en segundo plano cada cierto tiempo."""

import logging
import threading
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

    def __init__(self, jobs: list[Job], interval_seconds: float) -> None:
        self._jobs = jobs
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> None:
        """Ejecuta cada trabajo una vez."""
        for job in self._jobs:
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
        while True:
            self.run_once()
            if self._stop.wait(self._interval_seconds):
                return
