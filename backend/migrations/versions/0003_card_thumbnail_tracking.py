"""Seguimiento de la generación de la versión pequeña de las cartas.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "thumbnail_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "cards", sa.Column("thumbnail_last_error", sa.String(500), nullable=True)
    )
    op.add_column(
        "cards", sa.Column("thumbnail_claimed_until", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("cards") as batch:
        batch.drop_column("thumbnail_claimed_until")
        batch.drop_column("thumbnail_last_error")
        batch.drop_column("thumbnail_attempts")
