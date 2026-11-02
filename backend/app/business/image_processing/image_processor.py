"""Procesador de imágenes: valida formato, peso, proporción y resolución, y genera
la versión pequeña. No guarda nada: guardar es trabajo de la persistencia."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps

from app.business.image_processing.models import ImageInfo, ImageSpec, ProcessedImage
from app.business.shared.errors import ValidationFailedError

FIELD = "image"
ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
FORMAT_MESSAGE = "Formato de imagen no permitido. Use PNG, JPG o WebP."


def _format_megabytes(size: int) -> str:
    megabytes = size / (1024 * 1024)
    return f"{megabytes:g} MB"


class ImageProcessor:
    """Valida imágenes contra un ImageSpec y genera su versión pequeña."""

    def validate(self, data: bytes, spec: ImageSpec) -> ImageInfo:
        """Devuelve los datos de la imagen o lanza ValidationFailedError indicando
        el requisito incumplido."""
        image, image_format = self._load(data, spec)
        return ImageInfo(
            format=image_format,
            content_type=ALLOWED_FORMATS[image_format],
            width=image.width,
            height=image.height,
            size_bytes=len(data),
        )

    def create_thumbnail(self, data: bytes, spec: ImageSpec) -> ProcessedImage:
        """Genera la versión pequeña, con el tamaño exacto definido en el ImageSpec."""
        image, image_format = self._load(data, spec)
        image = self._normalize_mode(image, image_format)
        thumbnail = image.resize(spec.thumbnail_size, Image.Resampling.LANCZOS)

        buffer = BytesIO()
        options: dict[str, object] = {}
        if image_format == "PNG":
            options["optimize"] = True
        else:
            options["quality"] = 90
        thumbnail.save(buffer, format=image_format, **options)
        return ProcessedImage(
            data=buffer.getvalue(),
            content_type=ALLOWED_FORMATS[image_format],
            width=thumbnail.width,
            height=thumbnail.height,
        )

    def _load(self, data: bytes, spec: ImageSpec) -> tuple[Image.Image, str]:
        if len(data) > spec.max_bytes:
            raise ValidationFailedError(
                f"La imagen supera el máximo de {_format_megabytes(spec.max_bytes)}.",
                field=FIELD,
            )
        image, image_format = self._decode(data)

        ratio_w, ratio_h = spec.aspect_ratio
        # Comparación exacta con enteros: sin decimales ni tolerancias.
        if image.width * ratio_h != image.height * ratio_w:
            raise ValidationFailedError(
                f"La imagen debe tener proporción {ratio_w}:{ratio_h}.", field=FIELD
            )
        if image.width < spec.min_width or image.height < spec.min_height:
            raise ValidationFailedError(
                f"La imagen debe medir al menos {spec.min_width} × {spec.min_height} píxeles.",
                field=FIELD,
            )
        return image, image_format

    def _decode(self, data: bytes) -> tuple[Image.Image, str]:
        """Abre la imagen por su contenido real, no por su extensión ni su tipo declarado."""
        try:
            with warnings.catch_warnings():
                # Una imagen que Pillow considera una "bomba" se rechaza.
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as opened:
                    image_format = opened.format
                    if image_format not in ALLOWED_FORMATS:
                        raise ValidationFailedError(FORMAT_MESSAGE, field=FIELD)
                    # Respeta la orientación de las fotos de celular (EXIF).
                    oriented = ImageOps.exif_transpose(opened)
                    oriented.load()
        except ValidationFailedError:
            raise
        except (
            OSError,
            SyntaxError,
            ValueError,
            Warning,
            Image.DecompressionBombError,
        ):
            raise ValidationFailedError(FORMAT_MESSAGE, field=FIELD) from None
        assert image_format is not None
        return oriented, image_format

    @staticmethod
    def _normalize_mode(image: Image.Image, image_format: str) -> Image.Image:
        has_alpha = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
        if has_alpha and image_format != "JPEG":
            return image.convert("RGBA")
        return image.convert("RGB")
