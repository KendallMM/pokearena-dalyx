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


class FakeImageStore:
    """Almacén de imágenes en memoria. Registra el orden de las operaciones."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_delete = False

    def save_original(self, kind, data, info) -> str:
        image_id = f"img-{len(self.saved) + 1}"
        self.saved[image_id] = data
        self.events.append("image_saved")
        return image_id

    def delete(self, image_id: str) -> None:
        if self.fail_delete:
            raise RuntimeError("no se pudo borrar")
        self.deleted.append(image_id)
        self.saved.pop(image_id, None)


class FakeCardRepository:
    """Guarda cartas en memoria y asigna códigos por tipo, como lo hace MySQL."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.added: list = []
        self.fail_with: Exception | None = None
        self._counters: dict[str, int] = {}

    def add(self, card):
        from app.business.catalog.content.cards.card_code import build_card_code
        from app.business.catalog.content.cards.models import StoredCard

        self.events.append("card_added")
        if self.fail_with is not None:
            raise self.fail_with
        self._counters[card.card_type] = self._counters.get(card.card_type, 0) + 1
        self.added.append(card)
        return StoredCard(
            code=build_card_code(card.card_type, self._counters[card.card_type]),
            status=card.status,
        )
