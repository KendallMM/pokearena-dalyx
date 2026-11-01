"""Tablas de MySQL (modelos del ORM). Nombres en plural y snake_case."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base de todos los modelos."""


class CardTypeRow(Base):
    __tablename__ = "card_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)


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
