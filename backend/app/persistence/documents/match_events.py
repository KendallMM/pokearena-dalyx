"""Historial documental de partidas, idempotente por identificador de evento."""

from pymongo import timeout
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.business.automatic_tasks.match_events_job import PendingMatchEvent
from app.business.shared.errors import ServiceUnavailableError


class MongoMatchHistory:
    def __init__(self, collection) -> None:
        self.collection = collection

    def store(self, event: PendingMatchEvent, timeout_seconds: float) -> None:
        payload = {"match_id": event.match_id, **event.payload}
        try:
            with timeout(timeout_seconds):
                self._store_confirmed(event, payload)
        except PyMongoError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar el evento de partida."
            ) from exc

    def _store_confirmed(self, event: PendingMatchEvent, payload: dict) -> None:
        try:
            self.collection.update_one(
                {"_id": event.id}, {"$setOnInsert": payload}, upsert=True
            )
        except DuplicateKeyError:
            # Otra instancia pudo insertar el mismo identificador en paralelo.
            pass
        # Verifica el contenido por ID antes de confirmar una copia nueva o existente.
        if self.collection.find_one({"_id": event.id}) != {
            "_id": event.id,
            **payload,
        }:
            raise ServiceUnavailableError(
                "El historial no confirmó el evento esperado."
            )
