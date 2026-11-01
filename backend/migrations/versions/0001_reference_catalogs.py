"""Catálogos de referencia: tipos de carta, rarezas y habilidades (con HAB-000).

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

CARD_TYPES = [
    ("FUE", "Fuego"),
    ("AGU", "Agua"),
    ("PLA", "Planta"),
    ("ELE", "Eléctrico"),
    ("PSI", "Psíquico"),
    ("LUC", "Lucha"),
]
RARITIES = [
    ("COMMON", "Común"),
    ("UNCOMMON", "Poco común"),
    ("RARE", "Rara"),
    ("LEGENDARY", "Legendaria"),
]


def upgrade() -> None:
    card_types = op.create_table(
        "card_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.UniqueConstraint("code", name="uq_card_types_code"),
        sa.UniqueConstraint("name", name="uq_card_types_name"),
    )
    rarities = op.create_table(
        "rarities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.UniqueConstraint("code", name="uq_rarities_code"),
        sa.UniqueConstraint("name", name="uq_rarities_name"),
    )
    abilities = op.create_table(
        "abilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(7), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "affected_card_type_id",
            sa.Integer(),
            sa.ForeignKey("card_types.id", name="fk_abilities_card_types"),
            nullable=True,
        ),
        sa.UniqueConstraint("code", name="uq_abilities_code"),
    )

    # Tipos y rarezas son un catálogo cerrado: un valor nuevo requiere desarrollo.
    op.bulk_insert(card_types, [{"code": c, "name": n} for c, n in CARD_TYPES])
    op.bulk_insert(rarities, [{"code": c, "name": n} for c, n in RARITIES])
    # Sin Habilidad existe desde el inicio para poder crear cartas sin otras habilidades.
    op.bulk_insert(
        abilities,
        [{"code": "HAB-000", "name": "Sin Habilidad", "affected_card_type_id": None}],
    )


def downgrade() -> None:
    op.drop_table("abilities")
    op.drop_table("rarities")
    op.drop_table("card_types")
