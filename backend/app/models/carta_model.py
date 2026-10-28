"""Modelos SQL compartidos: base, habilidades, cartas, contadores de código,
trabajos de imagen e idempotencia (tablas en plural snake_case)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ======================================================================
# Base declarativa y utilidades
# ======================================================================

TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    """Fecha y hora UTC sin zona (así la guardan MySQL y SQLite por igual)."""
    return datetime.now(UTC).replace(tzinfo=None)


# ======================================================================
# Habilidades
# ======================================================================


class Ability(Base):
    """Habilidad de carta.

    Su creación es otro user story: aquí solo se necesita la tabla para
    asociar una carta con su habilidad (siempre existe ``HAB-000``).
    """

    __tablename__ = "abilities"
    __table_args__ = TABLE_OPTIONS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    trigger_type: Mapped[str | None] = mapped_column(String(30))
    condition_type: Mapped[str | None] = mapped_column(String(50))
    effect_type: Mapped[str | None] = mapped_column(String(50))
    target_type: Mapped[str | None] = mapped_column(String(50))
    affected_type: Mapped[str | None] = mapped_column(String(50))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ======================================================================
# Contador de consecutivos por tipo de carta
# ======================================================================


class CardCodeCounter(Base):
    """Último consecutivo usado por tipo de carta (un renglón por tipo)."""

    __tablename__ = "card_code_counters"
    __table_args__ = (
        CheckConstraint("last_number >= 0", name="ck_card_code_counters_last_number"),
        TABLE_OPTIONS,
    )

    card_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_number: Mapped[int] = mapped_column(default=0)


# ======================================================================
# Cartas
# ======================================================================


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("cost BETWEEN 0 AND 10", name="ck_cards_cost"),
        CheckConstraint("power BETWEEN -20 AND 20", name="ck_cards_power"),
        Index("ix_cards_name_search", "name_search"),
        Index("ix_cards_card_type", "card_type"),
        Index("ix_cards_rarity", "rarity"),
        Index("ix_cards_ability_id", "ability_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    name_search: Mapped[str] = mapped_column(String(255))
    cost: Mapped[int]
    power: Mapped[int]
    card_type: Mapped[str] = mapped_column(String(20))
    rarity: Mapped[str] = mapped_column(String(20))
    ability_id: Mapped[int] = mapped_column(ForeignKey("abilities.id"))
    evolution_target_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    image_ref: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    ability: Mapped[Ability] = relationship(lazy="raise")


# ======================================================================
# Trabajos de imagen (compartidos por cartas y ubicaciones)
# ======================================================================

JOB_PENDING = "PENDING"
JOB_PROCESSING = "PROCESSING"
JOB_RETRY = "RETRY"
JOB_DONE = "DONE"
JOB_FAILED = "FAILED"

ENTITY_CARD = "card"
ENTITY_LOCATION_VERSION = "location_version"


class ImageJob(Base):
    """Trabajo durable de procesamiento de imagen (miniatura + estado final)."""

    __tablename__ = "image_jobs"
    __table_args__ = (
        Index("ix_image_jobs_status_next", "status", "next_attempt_at"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int]
    image_ref: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default=JOB_PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


# ======================================================================
# Llaves de idempotencia (reemplazan a Redis)
# ======================================================================


class IdempotencyKey(Base):
    """Registro de solicitudes de creación ya procesadas (reemplaza a Redis)."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "endpoint", "key_value", name="uq_idempotency_keys_scope"
        ),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(100))
    key_value: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
