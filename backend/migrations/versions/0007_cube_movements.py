"""Historial de movimientos de cubos.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea el historial y registra los cubos iniciales ya entregados."""
    op.create_table(
        "cube_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("reason", "reference", name="uq_cube_movements_operation"),
        sa.CheckConstraint("amount <> 0", name="ck_cube_movements_amount"),
        sa.CheckConstraint("balance_after >= 0", name="ck_cube_movements_balance"),
    )
    op.create_index("ix_cube_movements_player", "cube_movements", ["player_id", "id"])
    # Las entregas anteriores a esta tabla también quedan en el historial,
    # para que su saldo coincida con sus movimientos.
    op.execute(
        "INSERT INTO cube_movements "
        "(player_id, amount, balance_after, reason, reference, created_at) "
        "SELECT player_id, cubes_granted, cubes_granted, 'initial_collection', "
        "player_id, COALESCE(delivered_at, CURRENT_TIMESTAMP) "
        "FROM initial_collection_deliveries "
        "WHERE status = 'delivered' AND cubes_granted > 0"
    )


def downgrade() -> None:
    op.drop_index("ix_cube_movements_player", table_name="cube_movements")
    op.drop_table("cube_movements")
