"""Requisitos de la imagen de una carta (historia Crear carta)."""

from app.business.image_processing.models import ImageSpec

# Versión grande: proporción vertical 5:7, mínimo 600 × 840, hasta 5 MB.
# Versión pequeña para el tablero: 200 × 280.
CARD_IMAGE_SPEC = ImageSpec(
    aspect_ratio=(5, 7),
    min_width=600,
    min_height=840,
    thumbnail_size=(200, 280),
)
