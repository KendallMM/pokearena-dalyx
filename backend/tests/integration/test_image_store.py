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


def test_read_original_returns_the_saved_bytes() -> None:
    store = MongoImageStore(mongomock.MongoClient().db["images"])
    image_id = store.save_original("card", b"\x89PNG", INFO)
    stored = store.read_original(image_id)
    assert (stored.data, stored.content_type) == (b"\x89PNG", "image/png")


def test_read_original_of_a_missing_image_fails() -> None:
    import pytest

    store = MongoImageStore(mongomock.MongoClient().db["images"])
    with pytest.raises(LookupError):
        store.read_original("0" * 24)


def test_save_thumbnail_is_stored_next_to_the_original_and_can_be_repeated() -> None:
    from app.business.image_processing.models import ProcessedImage

    collection = mongomock.MongoClient().db["images"]
    store = MongoImageStore(collection)
    image_id = store.save_original("card", b"original", INFO)
    store.save_thumbnail(image_id, ProcessedImage(b"t1", "image/png", 200, 280))
    store.save_thumbnail(image_id, ProcessedImage(b"t2", "image/png", 200, 280))
    document = collection.find_one({"_id": ObjectId(image_id)})
    assert bytes(document["original"]["data"]) == b"original"
    assert bytes(document["thumbnail"]["data"]) == b"t2"
    assert (document["thumbnail"]["width"], document["thumbnail"]["height"]) == (
        200,
        280,
    )


def test_save_thumbnail_of_a_missing_image_fails() -> None:
    import pytest

    from app.business.image_processing.models import ProcessedImage

    store = MongoImageStore(mongomock.MongoClient().db["images"])
    with pytest.raises(LookupError):
        store.save_thumbnail("0" * 24, ProcessedImage(b"t", "image/png", 200, 280))
