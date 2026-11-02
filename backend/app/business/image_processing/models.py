"""Reglas y resultados del procesamiento de imágenes."""

from dataclasses import dataclass

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


@dataclass(frozen=True)
class ImageSpec:
    """Requisitos de una imagen. Quien la usa (Cartas, Ubicaciones) define los suyos."""

    aspect_ratio: tuple[int, int]  # ancho:alto, por ejemplo (5, 7)
    min_width: int
    min_height: int
    thumbnail_size: tuple[int, int]  # ancho y alto de la versión pequeña
    max_bytes: int = MAX_IMAGE_BYTES

    def __post_init__(self) -> None:
        ratio_w, ratio_h = self.aspect_ratio
        thumb_w, thumb_h = self.thumbnail_size
        if thumb_w * ratio_h != thumb_h * ratio_w:
            raise ValueError(
                "La miniatura debe tener la misma proporción que la imagen."
            )


@dataclass(frozen=True)
class ImageInfo:
    """Datos de una imagen ya validada."""

    format: str  # PNG, JPEG o WEBP
    content_type: str
    width: int
    height: int
    size_bytes: int


@dataclass(frozen=True)
class ProcessedImage:
    """Imagen generada por el procesador (la versión pequeña)."""

    data: bytes
    content_type: str
    width: int
    height: int


@dataclass(frozen=True)
class StoredImage:
    """Imagen original leída del almacén."""

    data: bytes
    content_type: str
