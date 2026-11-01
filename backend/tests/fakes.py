"""Dobles de prueba para los puertos."""

from app.business.shared.ports import StoredResponse


class InMemoryIdempotencyStore:
    """Caché en memoria. Solo sirve en pruebas: no se comparte entre instancias."""

    def __init__(self) -> None:
        self.data: dict[str, StoredResponse] = {}
        self.saved_ttls: list[int] = []

    def get(self, key: str) -> StoredResponse | None:
        return self.data.get(key)

    def save(self, key: str, response: StoredResponse, ttl_seconds: int) -> None:
        self.data[key] = response
        self.saved_ttls.append(ttl_seconds)
