"""Imágenes en MongoDB. Colección `images`, campos en snake_case."""

from datetime import datetime, timezone
from typing import Any

from bson import Binary, ObjectId
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.business.image_processing.models import ImageInfo, ProcessedImage, StoredImage
from app.business.shared.errors import ServiceUnavailableError

# Proyección de MongoDB: 1 indica que el campo se incluye en el resultado.
INCLUDE_FIELD = 1
# Una actualización por identificador debe encontrar exactamente un documento.
EXPECTED_MATCHES = 1


class MongoImageStore:
    """Implementa el puerto ImageStore.

    Si MongoDB no responde, cada operación lanza ServiceUnavailableError (503).
    Así la capa de negocio detiene el flujo con un error del dominio y nunca
    continúa como si la imagen se hubiera guardado.
    """

    def __init__(self, collection: Collection) -> None:
        self._collection = collection

    def save_original(self, kind: str, data: bytes, info: ImageInfo) -> str:
        document: dict[str, Any] = {
            "kind": kind,
            "original": {
                "data": Binary(data),
                "content_type": info.content_type,
                "width": info.width,
                "height": info.height,
                "size_bytes": info.size_bytes,
            },
            # La versión pequeña la agrega la tarea automática (ADR-002).
            "thumbnail": None,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = self._collection.insert_one(document)
        except PyMongoError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar la imagen. Reintenta."
            ) from exc
        return str(result.inserted_id)

    def read_original(self, image_id: str) -> StoredImage:
        try:
            document = self._collection.find_one(
                {"_id": ObjectId(image_id)}, {"original": INCLUDE_FIELD}
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError(
                "No se pudo leer la imagen. Reintenta."
            ) from exc
        if document is None:
            raise LookupError(f"La imagen {image_id} no existe en el almacén.")
        original = document["original"]
        return StoredImage(
            data=bytes(original["data"]), content_type=original["content_type"]
        )

    def save_thumbnail(self, image_id: str, thumbnail: ProcessedImage) -> None:
        try:
            result = self._update_thumbnail(image_id, thumbnail)
        except PyMongoError as exc:
            raise ServiceUnavailableError(
                "No se pudo guardar la miniatura. Reintenta."
            ) from exc
        if result.matched_count != EXPECTED_MATCHES:
            raise LookupError(f"La imagen {image_id} no existe en el almacén.")

    def _update_thumbnail(self, image_id: str, thumbnail: ProcessedImage):
        return self._collection.update_one(
            {"_id": ObjectId(image_id)},
            {
                "$set": {
                    "thumbnail": {
                        "data": Binary(thumbnail.data),
                        "content_type": thumbnail.content_type,
                        "width": thumbnail.width,
                        "height": thumbnail.height,
                        "size_bytes": len(thumbnail.data),
                    }
                }
            },
        )

    def delete(self, image_id: str) -> None:
        try:
            self._collection.delete_one({"_id": ObjectId(image_id)})
        except PyMongoError as exc:
            raise ServiceUnavailableError(
                "No se pudo borrar la imagen. Reintenta."
            ) from exc
