"""Jugadores, identidad externa única y entrega inicial transaccional.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import VARCHAR

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea cuentas e identidades sin usar el correo como clave única."""
    op.create_table(
        "players",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="player"),
        sa.Column("elo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cubes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("cubes >= 0", name="ck_players_cubes"),
    )
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column(
            "subject",
            sa.String(255).with_variant(VARCHAR(255, collation="utf8mb4_bin"), "mysql"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "subject", name="uq_external_identities_provider_subject"
        ),
    )
    op.create_index(
        "ix_external_identities_player_id", "external_identities", ["player_id"]
    )
    op.create_table(
        "initial_collection_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.String(36),
            sa.ForeignKey("players.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("cubes_granted", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered')", name="ck_initial_delivery_status"
        ),
    )
    op.create_index(
        "ix_initial_deliveries_retry",
        "initial_collection_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_table(
        "player_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("player_id", "card_id", name="uq_player_cards_player_card"),
        sa.CheckConstraint("quantity > 0", name="ck_player_cards_quantity"),
    )


def downgrade() -> None:
    """Retira primero las tablas dependientes."""
    op.drop_table("player_cards")
    op.drop_table("initial_collection_deliveries")
    op.drop_table("external_identities")
    op.drop_table("players")
