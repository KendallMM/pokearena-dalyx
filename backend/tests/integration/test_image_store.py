"""MongoImageStore sobre una base simulada."""

import mongomock
from bson import ObjectId

from app.business.image_processing.models import ImageInfo
from app.persistence.documents.image_repository import MongoImageStore

INFO = ImageInfo("PNG", "image/png", 600, 840, 4)


def test_save_original_stores_the_image_with_pending_thumbnail() -> None:
    collection = mongomock.MongoClient().db["images"]
    image_id = MongoImageStore(collection).save_original("card", b"\x89PNG", INFO)
    document = collection.find_one({"_id": ObjectId(image_id)})
    assert document["kind"] == "card"
    assert bytes(document["original"]["data"]) == b"\x89PNG"
    assert document["original"]["content_type"] == "image/png"
    assert (document["original"]["width"], document["original"]["height"]) == (600, 840)
    assert document["thumbnail"] is None


def test_delete_removes_the_image() -> None:
    collection = mongomock.MongoClient().db["images"]
    store = MongoImageStore(collection)
    image_id = store.save_original("card", b"x", INFO)
    store.delete(image_id)
    assert collection.count_documents({}) == 0
