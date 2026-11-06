"""Tablas de MySQL (modelos del ORM). Nombres en plural y snake_case."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.mysql import VARCHAR
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
    # Nombre sin tildes ni mayúsculas, para buscar por coincidencia parcial.
    search_name: Mapped[str] = mapped_column(String(100), server_default=text("''"))
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


class LocationEffectTypeRow(Base):
    __tablename__ = "location_effect_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    # Parámetros que exige el tipo de efecto (ver la migración 0004).
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class LocationRow(Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("card_limit BETWEEN 0 AND 5", name="ck_locations_card_limit"),
        CheckConstraint(
            "extra_energy_amount >= 0 AND ("
            "(extra_energy_mode = 'fixed' AND extra_energy_amount <= 3) OR "
            "(extra_energy_mode = 'per_card' AND extra_energy_amount <= 2))",
            name="ck_locations_extra_energy",
        ),
        Index("ix_locations_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    card_limit: Mapped[int]
    extra_energy_mode: Mapped[str] = mapped_column(String(10))
    extra_energy_amount: Mapped[int]
    # NULL significa que la ubicación no tiene efecto.
    effect_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("location_effect_types.id"), nullable=True
    )
    effect_parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    # Identificador de la imagen en la base documental.
    image_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    # Seguimiento de la generación de la versión pequeña (fechas en UTC).
    thumbnail_attempts: Mapped[int] = mapped_column(server_default=text("0"))
    thumbnail_last_error: Mapped[str | None] = mapped_column(String(500))
    thumbnail_claimed_until: Mapped[datetime | None] = mapped_column(DateTime())


class PlayerRow(Base):
    """MySQL, mensaje 28: cuenta persistente con rol y Elo iniciales.

    Esta tabla guarda jugadores; las credenciales JWT se emiten por separado.
    """

    __tablename__ = "players"
    __table_args__ = (CheckConstraint("cubes >= 0", name="ck_players_cubes"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(30), server_default="player")
    elo: Mapped[int] = mapped_column(server_default=text("0"))
    cubes: Mapped[int] = mapped_column(server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class ExternalIdentityRow(Base):
    """MySQL, mensajes 24 y 29: asociación estable y única proveedor/sub."""

    __tablename__ = "external_identities"
    __table_args__ = (
        # La base de datos impide duplicados incluso si dos solicitudes vieron
        # que la identidad no existía. Buscar antes de insertar no basta.
        UniqueConstraint(
            "provider", "subject", name="uq_external_identities_provider_subject"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(
        String(255).with_variant(VARCHAR(255, collation="utf8mb4_bin"), "mysql")
    )


class InitialCollectionDeliveryRow(Base):
    """Solicitud durable creada en la misma transacción que el jugador."""

    __tablename__ = "initial_collection_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered')", name="ck_initial_delivery_status"
        ),
        Index("ix_initial_deliveries_retry", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now()
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime())
    cubes_granted: Mapped[int | None]


class PlayerCardRow(Base):
    """Cartas poseídas por el jugador; el catálogo conserva la definición."""

    __tablename__ = "player_cards"
    __table_args__ = (
        UniqueConstraint("player_id", "card_id", name="uq_player_cards_player_card"),
        CheckConstraint("quantity > 0", name="ck_player_cards_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    quantity: Mapped[int] = mapped_column(server_default=text("1"))
