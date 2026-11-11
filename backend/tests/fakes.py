"""Dobles de prueba para los puertos."""

from datetime import datetime, timedelta, timezone

from app.business.catalog.content.cards.models import CardStatus, PendingCard
from app.business.catalog.content.locations.models import (
    LocationStatus,
    PendingLocation,
    StoredLocation,
)
from app.business.catalog.references.models import (
    Ability,
    CardType,
    EffectParameter,
    LocationEffectType,
    Rarity,
)
from app.business.image_processing.models import StoredImage
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
        self.location_effect_types = [
            LocationEffectType(
                "type_bonus",
                "Bonificación por tipo",
                [
                    EffectParameter("card_type", "card_type", True),
                    EffectParameter("amount", "integer", True, -5, 5),
                ],
            ),
            LocationEffectType(
                "cost_modifier",
                "Modificador de costo",
                [
                    EffectParameter("amount", "integer", True, -5, 5),
                    EffectParameter("card_type", "card_type", False),
                ],
            ),
            LocationEffectType(
                "turn_restriction",
                "Restricción por turno",
                [EffectParameter("turns", "integer_list", True, 1, 6)],
            ),
        ]

    def list_card_types(self) -> list[CardType]:
        return list(self.card_types)

    def list_rarities(self) -> list[Rarity]:
        return list(self.rarities)

    def list_abilities(self) -> list[Ability]:
        return list(self.abilities)

    def list_location_effect_types(self) -> list[LocationEffectType]:
        return list(self.location_effect_types)


class FakeClock:
    """Reloj que se mueve a mano."""

    def __init__(self) -> None:
        self.current = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class FakeImageStore:
    """Almacén de imágenes en memoria. Registra el orden de las operaciones."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.saved: dict[str, bytes] = {}
        self.thumbnails: dict[str, object] = {}
        self.deleted: list[str] = []
        self.fail_delete = False
        self.fail_read = False
        self.fail_thumbnail_save = False

    def save_original(self, kind, data, info) -> str:
        image_id = f"img-{len(self.saved) + 1}"
        self.saved[image_id] = data
        self.events.append("image_saved")
        return image_id

    def read_original(self, image_id: str) -> StoredImage:
        if self.fail_read:
            raise RuntimeError("MongoDB no responde")
        return StoredImage(data=self.saved[image_id], content_type="image/png")

    def save_thumbnail(self, image_id: str, thumbnail) -> None:
        if self.fail_thumbnail_save:
            raise RuntimeError("no se pudo guardar la miniatura")
        self.thumbnails[image_id] = thumbnail

    def delete(self, image_id: str) -> None:
        if self.fail_delete:
            raise RuntimeError("no se pudo borrar")
        self.deleted.append(image_id)
        self.saved.pop(image_id, None)


class FakeCardRepository:
    """Guarda cartas en memoria, asigna códigos y reserva pendientes como MySQL."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.added: list = []
        self.fail_with: Exception | None = None
        self._counters: dict[str, int] = {}
        # id -> estado de seguimiento
        self.rows: dict[int, dict] = {}

    def add(self, card):
        from app.business.catalog.content.cards.card_code import build_card_code
        from app.business.catalog.content.cards.models import StoredCard

        self.events.append("card_added")
        if self.fail_with is not None:
            raise self.fail_with
        self._counters[card.card_type] = self._counters.get(card.card_type, 0) + 1
        self.added.append(card)
        code = build_card_code(card.card_type, self._counters[card.card_type])
        self.rows[len(self.rows) + 1] = {
            "code": code,
            "image_id": card.image_id,
            "status": card.status,
            "claimed_until": None,
            "attempts": 0,
            "last_error": None,
        }
        return StoredCard(code=code, status=card.status)

    def claim_pending_thumbnails(self, now, limit, lease_seconds):
        claimed = []
        for card_id, row in self.rows.items():
            free = row["claimed_until"] is None or row["claimed_until"] <= now
            if row["status"] is CardStatus.PENDING_THUMBNAIL and free:
                row["claimed_until"] = now + timedelta(seconds=lease_seconds)
                claimed.append(PendingCard(card_id, row["code"], row["image_id"]))
            if len(claimed) == limit:
                break
        return claimed

    def mark_available(self, card_id: int) -> None:
        row = self.rows[card_id]
        row.update(status=CardStatus.AVAILABLE, claimed_until=None, last_error=None)

    def register_thumbnail_failure(self, card_id, error, retry_at) -> None:
        row = self.rows[card_id]
        row["attempts"] += 1
        row["last_error"] = error
        row["claimed_until"] = retry_at


class FakeLocationRepository:
    """Guarda ubicaciones en memoria y reserva pendientes como MySQL."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.added: list = []
        self.fail_with: Exception | None = None
        self.rows: dict[int, dict] = {}

    def add(self, location):
        self.events.append("location_added")
        if self.fail_with is not None:
            raise self.fail_with
        self.added.append(location)
        location_id = len(self.rows) + 1
        self.rows[location_id] = {
            "image_id": location.image_id,
            "status": location.status,
            "claimed_until": None,
            "attempts": 0,
            "last_error": None,
        }
        return StoredLocation(id=location_id, status=location.status)

    def claim_pending_thumbnails(self, now, limit, lease_seconds):
        claimed = []
        for location_id, row in self.rows.items():
            free = row["claimed_until"] is None or row["claimed_until"] <= now
            if row["status"] is LocationStatus.PENDING_THUMBNAIL and free:
                row["claimed_until"] = now + timedelta(seconds=lease_seconds)
                claimed.append(PendingLocation(location_id, row["image_id"]))
            if len(claimed) == limit:
                break
        return claimed

    def mark_available(self, location_id: int) -> None:
        row = self.rows[location_id]
        row.update(status=LocationStatus.AVAILABLE, claimed_until=None, last_error=None)

    def register_thumbnail_failure(self, location_id, error, retry_at) -> None:
        row = self.rows[location_id]
        row["attempts"] += 1
        row["last_error"] = error
        row["claimed_until"] = retry_at


class FakeCardSearchRepository:
    """Búsqueda en memoria: devuelve lo que se le configure y anota cómo la llamaron."""

    def __init__(self) -> None:
        self.results: list = []
        self.calls: list[tuple] = []
        self.image_ids: dict[str, str] = {}

    def search(self, criteria, after_id, limit):
        self.calls.append((criteria, after_id, limit))
        return [card for card in self.results if card.id > after_id][:limit]

    def find_image_id(self, code, only_available=False):
        return self.image_ids.get(code)
