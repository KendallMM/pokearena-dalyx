"""Tarea de miniaturas en CardService (ADR-002)."""

from io import BytesIO

from PIL import Image

from app.business.catalog.content.cards.models import (
    CardStatus,
    CreateCard,
    ThumbnailPolicy,
)
from app.business.catalog.content.cards.card_service import CardService
from app.business.image_processing.image_processor import ImageProcessor
from tests.unit.image_helpers import make_image


def _create(card_service, card_type="FUE") -> str:
    return card_service.create_card(
        CreateCard(
            "Charmander", 3, 5, card_type, "COMMON", "HAB-000", make_image(1000, 1400)
        )
    ).code


def _status(card_repository, number=1):
    return card_repository.rows[number]["status"]


def test_pending_card_becomes_available_with_exact_thumbnail(
    card_service, card_repository, image_store
) -> None:
    _create(card_service)
    result = card_service.process_pending_thumbnails()
    assert (result.processed, result.failed) == (1, 0)
    assert _status(card_repository) is CardStatus.AVAILABLE
    thumbnail = image_store.thumbnails["img-1"]
    assert (thumbnail.width, thumbnail.height) == (200, 280)
    with Image.open(BytesIO(thumbnail.data)) as decoded:
        assert decoded.size == (200, 280)


def test_nothing_is_processed_when_there_are_no_pending_cards(card_service) -> None:
    result = card_service.process_pending_thumbnails()
    assert (result.processed, result.failed) == (0, 0)


def test_available_cards_are_not_processed_again(card_service) -> None:
    _create(card_service)
    card_service.process_pending_thumbnails()
    assert card_service.process_pending_thumbnails().processed == 0


def test_card_is_not_available_when_the_thumbnail_cannot_be_read(
    card_service, card_repository, image_store, clock
) -> None:
    _create(card_service)
    image_store.fail_read = True
    result = card_service.process_pending_thumbnails()
    row = card_repository.rows[1]
    assert (result.processed, result.failed) == (0, 1)
    assert row["status"] is CardStatus.PENDING_THUMBNAIL
    assert row["attempts"] == 1
    assert "MongoDB no responde" in row["last_error"]


def test_card_is_not_available_if_saving_the_thumbnail_fails(
    card_service, card_repository, image_store
) -> None:
    """Nunca queda disponible con una imagen faltante."""
    _create(card_service)
    image_store.fail_thumbnail_save = True
    card_service.process_pending_thumbnails()
    assert _status(card_repository) is CardStatus.PENDING_THUMBNAIL


def test_card_with_a_corrupt_original_stays_pending(
    card_service, card_repository, image_store
) -> None:
    _create(card_service)
    image_store.saved["img-1"] = b"corrupta"
    card_service.process_pending_thumbnails()
    assert _status(card_repository) is CardStatus.PENDING_THUMBNAIL
    assert card_repository.rows[1]["attempts"] == 1


def test_failed_card_is_retried_after_the_retry_delay_and_then_succeeds(
    card_service, card_repository, image_store, clock
) -> None:
    _create(card_service)
    image_store.fail_read = True
    card_service.process_pending_thumbnails()

    image_store.fail_read = False
    clock.advance(30)  # todavía dentro de la espera: no se reintenta
    assert card_service.process_pending_thumbnails().processed == 0
    assert _status(card_repository) is CardStatus.PENDING_THUMBNAIL

    clock.advance(31)  # pasó la espera de 60 s
    result = card_service.process_pending_thumbnails()
    assert (result.processed, result.failed) == (1, 0)
    assert _status(card_repository) is CardStatus.AVAILABLE
    assert card_repository.rows[1]["last_error"] is None


def test_retry_keeps_counting_attempts(
    card_service, card_repository, image_store, clock
) -> None:
    _create(card_service)
    image_store.fail_read = True
    for _ in range(3):
        card_service.process_pending_thumbnails()
        clock.advance(61)
    assert card_repository.rows[1]["attempts"] == 3
    assert _status(card_repository) is CardStatus.PENDING_THUMBNAIL


def test_one_failing_card_does_not_block_the_others(
    card_service, card_repository, image_store
) -> None:
    _create(card_service)
    _create(card_service)
    _create(card_service)
    image_store.saved["img-2"] = b"corrupta"
    result = card_service.process_pending_thumbnails()
    assert (result.processed, result.failed) == (2, 1)
    assert _status(card_repository, 1) is CardStatus.AVAILABLE
    assert _status(card_repository, 2) is CardStatus.PENDING_THUMBNAIL
    assert _status(card_repository, 3) is CardStatus.AVAILABLE


def test_a_second_instance_does_not_take_cards_already_reserved(
    card_service, reference_repository, image_store, card_repository, clock
) -> None:
    other_instance = CardService(
        references=card_service._references,
        image_processor=ImageProcessor(),
        image_store=image_store,
        cards=card_repository,
        clock=clock,
    )
    _create(card_service)
    claimed = card_repository.claim_pending_thumbnails(clock.now(), 10, 120)
    assert len(claimed) == 1
    assert other_instance.process_pending_thumbnails().processed == 0


def test_reservation_expires_so_a_crashed_instance_does_not_block_the_card(
    card_service, card_repository, clock
) -> None:
    _create(card_service)
    card_repository.claim_pending_thumbnails(clock.now(), 10, 120)  # "se cayó"
    clock.advance(121)
    assert card_service.process_pending_thumbnails().processed == 1


def test_batch_size_limits_each_run(
    reference_repository, image_store, card_repository, clock, card_service
) -> None:
    limited = CardService(
        references=card_service._references,
        image_processor=ImageProcessor(),
        image_store=image_store,
        cards=card_repository,
        clock=clock,
        thumbnail_policy=ThumbnailPolicy(batch_size=2),
    )
    for _ in range(5):
        _create(card_service)
    assert limited.process_pending_thumbnails().processed == 2
    assert limited.process_pending_thumbnails().processed == 2
    assert limited.process_pending_thumbnails().processed == 1
    assert limited.process_pending_thumbnails().processed == 0
