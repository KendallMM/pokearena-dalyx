"""Utilidades compartidas por las pruebas."""

import io
import time

import jwt
from PIL import Image

JWT_SECRET = "test-secret-test-secret-test-secret-123"
CURSOR_SECRET = "cursor-secret-cursor-secret-cursor-1234"


def make_token(
    sub: str = "admin-1",
    role: str | None = "admin",
    *,
    secret: str = JWT_SECRET,
    expires_in: int = 3600,
    algorithm: str = "HS256",
    **extra,
) -> str:
    claims = {"sub": sub, "exp": int(time.time()) + expires_in, **extra}
    if role is not None:
        claims["role"] = role
    return jwt.encode(claims, secret, algorithm=algorithm)


def auth(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or make_token()}"}


def make_image(width: int, height: int, image_format: str = "PNG", mode: str = "RGB"):
    image = Image.new(mode, (width, height), (200, 80, 40) if mode == "RGB" else 128)
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def card_image(image_format: str = "PNG") -> bytes:
    return make_image(600, 840, image_format)


def location_image(image_format: str = "PNG") -> bytes:
    return make_image(800, 600, image_format)


def pad_to(data: bytes, size: int) -> bytes:
    """Agranda un archivo válido con bytes finales (los lectores los ignoran)."""
    assert len(data) <= size
    return data + b"\0" * (size - len(data))


def card_fields(**overrides) -> dict[str, str]:
    fields = {
        "name": "Pikachu",
        "cost": "3",
        "power": "5",
        "type": "Eléctrico",
        "rarity": "Común",
        "ability": "HAB-000",
    }
    fields.update({k: v for k, v in overrides.items()})
    return {k: v for k, v in fields.items() if v is not None}


def location_fields(**overrides) -> dict:
    fields = {
        "name": "Bosque Verde",
        "description": "Un bosque denso.",
        "card_limit": "4",
        "extra_energy_mode": "fixed",
        "extra_energy_amount": "1",
    }
    fields.update(overrides)
    return {k: v for k, v in fields.items() if v is not None}
