"""Genera imágenes de prueba en memoria."""

from io import BytesIO

from PIL import Image


def make_image(
    width: int,
    height: int,
    image_format: str = "PNG",
    mode: str = "RGB",
    **save_options,
) -> bytes:
    color = (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)
    image = Image.new(mode, (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format=image_format, **save_options)
    return buffer.getvalue()
