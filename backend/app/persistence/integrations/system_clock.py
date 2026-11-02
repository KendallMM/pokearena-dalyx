"""Reloj del servidor."""

from datetime import datetime, timezone


class SystemClock:
    """Implementa el puerto Clock con la hora real en UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
