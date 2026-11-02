"""Imágenes en MongoDB. Colección `images`, campos en snake_case."""

from datetime import datetime, timezone
from typing import Any

from bson import Binary, ObjectId
from pymongo.collection import Collection

from app.business.image_processing.models import ImageInfo


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

    def delete(self, image_id: str) -> None:
        self._collection.delete_one({"_id": ObjectId(image_id)})
