"""Decks de los jugadores y sus cartas.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("name_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("player_id", "name_key", name="uq_decks_player_name"),
    )
    op.create_table(
        "deck_cards",
        sa.Column(
            "deck_id", sa.String(36), sa.ForeignKey("decks.id"), primary_key=True
        ),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("cards.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("deck_cards")
    op.drop_table("decks")
