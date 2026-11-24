"""Actividad, expiración y rival bot de una partida."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None
STATUS = "status IN ('waiting', 'reserved', 'bot', 'found', 'cancelled', 'expired')"


def replace_open_player(batch, states: str) -> None:
    batch.drop_constraint("uq_search_open_player", type_="unique")
    batch.drop_column("open_player_id")
    batch.add_column(
        sa.Column(
            "open_player_id",
            sa.String(36),
            sa.Computed(f"CASE WHEN status IN ({states}) THEN player_id ELSE NULL END"),
        )
    )
    batch.create_unique_constraint("uq_search_open_player", ["open_player_id"])


def upgrade() -> None:
    last_seen_type = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.add_column("match_searches", sa.Column("last_seen_at", last_seen_type))
    # Conserva las búsquedas previas y usa su inicio como primera actividad.
    op.execute("UPDATE match_searches SET last_seen_at = created_at")
    with op.batch_alter_table("match_searches") as batch:
        replace_open_player(batch, "'waiting', 'reserved', 'bot'")
        batch.drop_constraint("ck_search_status", type_="check")
        batch.create_check_constraint("ck_search_status", STATUS)
        batch.alter_column("last_seen_at", existing_type=last_seen_type, nullable=False)
        batch.create_index("ix_search_activity", ["status", "last_seen_at"])
    with op.batch_alter_table("matches") as batch:
        batch.add_column(sa.Column("bot_card_ids", sa.JSON(none_as_null=True)))
        batch.drop_constraint("ck_matches_mode", type_="check")
        batch.create_check_constraint(
            "ck_matches_mode", "mode IN ('ranked', 'tournament', 'bot')"
        )
        batch.create_check_constraint(
            "ck_matches_bot",
            "(mode = 'bot' AND bot_card_ids IS NOT NULL) OR (mode <> 'bot' AND bot_card_ids IS NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM matches WHERE mode = 'bot'")):
        raise RuntimeError("La revisión 0009 no admite partidas contra el bot.")
    op.execute(
        "UPDATE match_searches SET status = 'cancelled' WHERE status = 'expired'"
    )
    with op.batch_alter_table("match_searches") as batch:
        replace_open_player(batch, "'waiting', 'reserved'")
        batch.drop_index("ix_search_activity")
        batch.drop_column("last_seen_at")
        batch.drop_constraint("ck_search_status", type_="check")
        batch.create_check_constraint(
            "ck_search_status",
            "status IN ('waiting', 'reserved', 'found', 'cancelled')",
        )
    with op.batch_alter_table("matches") as batch:
        batch.drop_constraint("ck_matches_bot", type_="check")
        batch.drop_constraint("ck_matches_mode", type_="check")
        batch.drop_column("bot_card_ids")
        batch.create_check_constraint(
            "ck_matches_mode", "mode IN ('ranked', 'tournament')"
        )
