"""Requisitos de la imagen de una ubicación (historia Crear ubicación)."""

from app.business.image_processing.models import ImageSpec

# Versión grande: proporción horizontal 4:3, mínimo 800 × 600, hasta 5 MB.
# Versión pequeña para el tablero: 320 × 240.
LOCATION_IMAGE_SPEC = ImageSpec(
    aspect_ratio=(4, 3),
    min_width=800,
    min_height=600,
    thumbnail_size=(320, 240),
)
