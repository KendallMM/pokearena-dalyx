"""Tablas de MySQL (modelos del ORM). Nombres en plural y snake_case."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base de todos los modelos."""


class CardTypeRow(Base):
    __tablename__ = "card_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    # Último consecutivo usado en los códigos PKA-<TIPO>-<NNN> de este tipo.
    last_card_number: Mapped[int] = mapped_column(server_default=text("0"))


class RarityRow(Base):
    __tablename__ = "rarities"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)


class AbilityRow(Base):
    __tablename__ = "abilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(7), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    # NULL significa que la habilidad afecta a todos los tipos.
    affected_card_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("card_types.id"), nullable=True
    )
    affected_card_type: Mapped[CardTypeRow | None] = relationship()


class CardRow(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("cost BETWEEN 0 AND 10", name="ck_cards_cost"),
        CheckConstraint("power BETWEEN -20 AND 20", name="ck_cards_power"),
        Index("ix_cards_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    cost: Mapped[int]
    power: Mapped[int]
    card_type_id: Mapped[int] = mapped_column(ForeignKey("card_types.id"))
    rarity_id: Mapped[int] = mapped_column(ForeignKey("rarities.id"))
    ability_id: Mapped[int] = mapped_column(ForeignKey("abilities.id"))
    # Identificador de la imagen en la base documental.
    image_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    # Seguimiento de la generación de la versión pequeña (fechas en UTC).
    thumbnail_attempts: Mapped[int] = mapped_column(server_default=text("0"))
    thumbnail_last_error: Mapped[str | None] = mapped_column(String(500))
    thumbnail_claimed_until: Mapped[datetime | None] = mapped_column(DateTime())
