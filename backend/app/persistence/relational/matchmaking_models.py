"""Tablas de búsquedas y partidas."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from app.persistence.relational.models import Base


def define_matchmaking_tables(
    metadata: sa.MetaData,
) -> tuple[sa.Table, sa.Table, sa.Table, sa.Table]:
    matches = sa.Table(
        "matches",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("bot_card_ids", sa.JSON(none_as_null=True)),
        sa.Column("initial_state", sa.JSON(none_as_null=True)),
        sa.CheckConstraint(
            "mode IN ('ranked', 'tournament', 'bot')", name="ck_matches_mode"
        ),
        sa.CheckConstraint(
            "(mode = 'bot' AND bot_card_ids IS NOT NULL) OR (mode <> 'bot' AND bot_card_ids IS NULL)",
            name="ck_matches_bot",
        ),
    )
    participants = sa.Table(
        "match_players",
        metadata,
        sa.Column(
            "match_id", sa.String(36), sa.ForeignKey("matches.id"), primary_key=True
        ),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), primary_key=True
        ),
        sa.Column("deck_id", sa.String(36), sa.ForeignKey("decks.id"), nullable=False),
        sa.Column("card_ids", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "active_player_id",
            sa.String(36),
            sa.Computed("CASE WHEN active = 1 THEN player_id ELSE NULL END"),
        ),
        sa.UniqueConstraint("active_player_id", name="uq_match_active_player"),
    )
    searches = sa.Table(
        "match_searches",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("deck_id", sa.String(36), sa.ForeignKey("decks.id"), nullable=False),
        sa.Column("card_ids", sa.JSON(), nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id")),
        sa.Column("error", sa.String(255)),
        sa.Column(
            "last_seen_at",
            sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Index("ix_search_activity", "status", "last_seen_at"),
        sa.Column(
            "open_player_id",
            sa.String(36),
            sa.Computed(
                "CASE WHEN status IN ('waiting', 'reserved', 'bot') THEN player_id ELSE NULL END"
            ),
        ),
        sa.UniqueConstraint("open_player_id", name="uq_search_open_player"),
        sa.CheckConstraint("mode IN ('ranked', 'tournament')", name="ck_search_mode"),
        sa.CheckConstraint(
            "status IN ('waiting', 'reserved', 'bot', 'found', 'cancelled', 'expired')",
            name="ck_search_status",
        ),
        sa.CheckConstraint(
            "(status = 'found' AND match_id IS NOT NULL) OR (status <> 'found' AND match_id IS NULL)",
            name="ck_search_match",
        ),
        sa.Index("ix_search_queue", "mode", "status", "created_at", "id"),
    )
    operations = sa.Table(
        "match_search_operations",
        metadata,
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), primary_key=True
        ),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column(
            "search_id",
            sa.String(36),
            sa.ForeignKey("match_searches.id"),
            nullable=False,
        ),
    )
    return matches, participants, searches, operations


matches, match_players, match_searches, match_search_operations = (
    define_matchmaking_tables(Base.metadata)
)


pending_match_events = sa.Table(
    "pending_match_events",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id"), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
    ),
    sa.Column("copied", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Index("ix_pending_match_events", "copied", "created_at", "id"),
)
