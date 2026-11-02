"""Procesador de imágenes con los requisitos de la carta."""

from io import BytesIO

import pytest
from PIL import Image

from app.business.catalog.content.cards.card_image_spec import CARD_IMAGE_SPEC
from app.business.image_processing.image_processor import ImageProcessor
from app.business.image_processing.models import ImageSpec
from app.business.shared.errors import ValidationFailedError
from tests.unit.image_helpers import make_image

processor = ImageProcessor()


def _reject(data: bytes, spec: ImageSpec = CARD_IMAGE_SPEC) -> ValidationFailedError:
    with pytest.raises(ValidationFailedError) as error:
        processor.validate(data, spec)
    assert error.value.field == "image"
    return error.value


@pytest.mark.parametrize(
    ("image_format", "content_type"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
)
def test_accepts_allowed_formats_at_minimum_size(image_format, content_type) -> None:
    info = processor.validate(make_image(600, 840, image_format), CARD_IMAGE_SPEC)
    assert (info.format, info.content_type) == (image_format, content_type)
    assert (info.width, info.height) == (600, 840)


def test_accepts_larger_image_with_exact_ratio() -> None:
    info = processor.validate(make_image(1000, 1400), CARD_IMAGE_SPEC)
    assert (info.width, info.height) == (1000, 1400)


@pytest.mark.parametrize("image_format", ["GIF", "BMP", "TIFF"])
def test_rejects_formats_not_allowed(image_format) -> None:
    error = _reject(make_image(600, 840, image_format))
    assert "PNG, JPG o WebP" in error.message


def test_rejects_content_that_is_not_an_image_whatever_its_name() -> None:
    assert "Formato" in _reject(b"esto no es una imagen").message
    assert "Formato" in _reject(b"").message


def test_rejects_truncated_image() -> None:
    data = make_image(600, 840)
    assert "Formato" in _reject(data[: len(data) // 2]).message


def test_rejects_image_over_5_mb_before_decoding() -> None:
    too_big = b"x" * (5 * 1024 * 1024 + 1)
    assert "5 MB" in _reject(too_big).message


def test_size_limit_comes_from_the_spec() -> None:
    small_limit = ImageSpec((5, 7), 600, 840, (200, 280), max_bytes=1000)
    assert "MB" in _reject(make_image(600, 840), small_limit).message


@pytest.mark.parametrize("size", [(840, 600), (600, 600), (601, 840), (1000, 1399)])
def test_rejects_wrong_ratio(size) -> None:
    assert "5:7" in _reject(make_image(*size)).message


@pytest.mark.parametrize("size", [(500, 700), (595, 833), (100, 140), (300, 420)])
def test_rejects_resolution_below_minimum(size) -> None:
    # 5:7 exacto pero pequeño: falla por resolución, no por proporción.
    message = _reject(make_image(*size)).message
    assert "600 × 840" in message


def test_respects_exif_orientation_of_phone_photos() -> None:
    """Una foto guardada como 840×600 con orientación 6 se ve vertical, 600×840."""
    image = Image.new("RGB", (840, 600), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    info = processor.validate(buffer.getvalue(), CARD_IMAGE_SPEC)
    assert (info.width, info.height) == (600, 840)


def test_rejects_decompression_bomb(monkeypatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    assert "Formato" in _reject(make_image(600, 840)).message


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_thumbnail_has_exact_size_and_same_format(image_format) -> None:
    thumbnail = processor.create_thumbnail(
        make_image(1000, 1400, image_format), CARD_IMAGE_SPEC
    )
    assert (thumbnail.width, thumbnail.height) == (200, 280)
    with Image.open(BytesIO(thumbnail.data)) as result:
        assert result.size == (200, 280)
        assert result.format == image_format


def test_thumbnail_keeps_transparency_in_png() -> None:
    thumbnail = processor.create_thumbnail(
        make_image(600, 840, "PNG", mode="RGBA"), CARD_IMAGE_SPEC
    )
    with Image.open(BytesIO(thumbnail.data)) as result:
        assert result.mode == "RGBA"
        assert result.getpixel((10, 10))[3] == 128


def test_thumbnail_from_palette_png() -> None:
    palette = Image.new("RGB", (600, 840), (1, 2, 3)).convert("P")
    buffer = BytesIO()
    palette.save(buffer, format="PNG")
    thumbnail = processor.create_thumbnail(buffer.getvalue(), CARD_IMAGE_SPEC)
    assert (thumbnail.width, thumbnail.height) == (200, 280)


def test_thumbnail_of_invalid_image_is_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        processor.create_thumbnail(make_image(840, 600), CARD_IMAGE_SPEC)


def test_card_spec_matches_the_story() -> None:
    assert CARD_IMAGE_SPEC.aspect_ratio == (5, 7)
    assert (CARD_IMAGE_SPEC.min_width, CARD_IMAGE_SPEC.min_height) == (600, 840)
    assert CARD_IMAGE_SPEC.thumbnail_size == (200, 280)
    assert CARD_IMAGE_SPEC.max_bytes == 5 * 1024 * 1024


def test_spec_requires_thumbnail_with_same_ratio() -> None:
    with pytest.raises(ValueError):
        ImageSpec((5, 7), 600, 840, (200, 200))
