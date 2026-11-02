"""Imágenes en MongoDB. Colección `images`, campos en snake_case."""

from datetime import datetime, timezone
from typing import Any

from bson import Binary, ObjectId
from pymongo.collection import Collection

from app.business.image_processing.models import ImageInfo, ProcessedImage, StoredImage


class MongoImageStore:
    """Implementa el puerto ImageStore."""

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
        return str(self._collection.insert_one(document).inserted_id)

    def read_original(self, image_id: str) -> StoredImage:
        document = self._collection.find_one(
            {"_id": ObjectId(image_id)}, {"original": 1}
        )
        if document is None:
            raise LookupError(f"La imagen {image_id} no existe en el almacén.")
        original = document["original"]
        return StoredImage(
            data=bytes(original["data"]), content_type=original["content_type"]
        )

    def save_thumbnail(self, image_id: str, thumbnail: ProcessedImage) -> None:
        result = self._collection.update_one(
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
        if result.matched_count != 1:
            raise LookupError(f"La imagen {image_id} no existe en el almacén.")

    def delete(self, image_id: str) -> None:
        self._collection.delete_one({"_id": ObjectId(image_id)})
