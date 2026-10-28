"""Modelos SQL de ubicaciones (con versionado)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.carta_model import (
    TABLE_OPTIONS,
    Base,
    utc_now,
)

# ======================================================================
# Ubicaciones y sus versiones
# ======================================================================


class GameLocation(Base):
    """Ubicación del juego. Su configuración vive en ``game_location_versions``."""

    __tablename__ = "game_locations"
    __table_args__ = TABLE_OPTIONS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameLocationVersion(Base):
    __tablename__ = "game_location_versions"
    __table_args__ = (
        UniqueConstraint(
            "game_location_id", "version", name="uq_game_location_versions_version"
        ),
        CheckConstraint(
            "card_limit BETWEEN 0 AND 5", name="ck_game_location_versions_card_limit"
        ),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_location_id: Mapped[int] = mapped_column(ForeignKey("game_locations.id"))
    version: Mapped[int]
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    effect_type: Mapped[str | None] = mapped_column(String(30))
    effect_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    card_limit: Mapped[int]
    extra_energy_mode: Mapped[str] = mapped_column(String(20))
    extra_energy_amount: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    image_ref: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
