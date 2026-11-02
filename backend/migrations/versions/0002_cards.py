"""Cartas: tabla cards y consecutivo por tipo para el código PKA-<TIPO>-<NNN>.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_types",
        sa.Column(
            "last_card_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("power", sa.Integer(), nullable=False),
        sa.Column(
            "card_type_id",
            sa.Integer(),
            sa.ForeignKey("card_types.id", name="fk_cards_card_types"),
            nullable=False,
        ),
        sa.Column(
            "rarity_id",
            sa.Integer(),
            sa.ForeignKey("rarities.id", name="fk_cards_rarities"),
            nullable=False,
        ),
        sa.Column(
            "ability_id",
            sa.Integer(),
            sa.ForeignKey("abilities.id", name="fk_cards_abilities"),
            nullable=False,
        ),
        sa.Column("image_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("code", name="uq_cards_code"),
        sa.CheckConstraint("cost BETWEEN 0 AND 10", name="ck_cards_cost"),
        sa.CheckConstraint("power BETWEEN -20 AND 20", name="ck_cards_power"),
    )
    op.create_index("ix_cards_status", "cards", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cards_status", table_name="cards")
    op.drop_table("cards")
    with op.batch_alter_table("card_types") as batch:
        batch.drop_column("last_card_number")
