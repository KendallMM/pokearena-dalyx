"""Guarda el estado inicial y el evento pendiente de la partida."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("initial_state", sa.JSON(), nullable=True))
    op.create_table(
        "pending_match_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "match_id", sa.String(36), sa.ForeignKey("matches.id"), nullable=False
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("copied", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_pending_match_events",
        "pending_match_events",
        ["copied", "created_at", "id"],
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT id FROM pending_match_events LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "La revisión contiene historial de partidas y no puede revertirse."
        )
    op.drop_table("pending_match_events")
    with op.batch_alter_table("matches") as batch:
        batch.drop_column("initial_state")
