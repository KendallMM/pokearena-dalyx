"""Dobles de prueba para los puertos."""

from app.business.catalog.references.models import Ability, CardType, Rarity
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


class FakeReferenceRepository:
    """Repositorio de referencias en memoria."""

    def __init__(self) -> None:
        self.card_types = [CardType("FUE", "Fuego"), CardType("AGU", "Agua")]
        self.rarities = [Rarity("COMMON", "Común"), Rarity("RARE", "Rara")]
        self.abilities = [Ability("HAB-000", "Sin Habilidad", None)]

    def list_card_types(self) -> list[CardType]:
        return list(self.card_types)

    def list_rarities(self) -> list[Rarity]:
        return list(self.rarities)

    def list_abilities(self) -> list[Ability]:
        return list(self.abilities)
