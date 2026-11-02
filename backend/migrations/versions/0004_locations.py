"""Ubicaciones: catálogo de tipos de efecto y tabla locations.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _integer(name: str, minimum: int, maximum: int, required: bool = True) -> dict:
    return {
        "name": name,
        "kind": "integer",
        "required": required,
        "minimum": minimum,
        "maximum": maximum,
    }


# Catálogo de la historia Crear ubicación. Cada tipo declara los parámetros que exige
# y la validación los lee de aquí, de modo que un tipo nuevo es un dato nuevo.
EFFECT_TYPES = [
    (
        "type_bonus",
        "Bonificación por tipo",
        [
            {"name": "card_type", "kind": "card_type", "required": True},
            _integer("amount", -5, 5),
        ],
    ),
    (
        "cost_modifier",
        "Modificador de costo",
        [
            _integer("amount", -5, 5),
            {"name": "card_type", "kind": "card_type", "required": False},
        ],
    ),
    (
        "turn_restriction",
        "Restricción por turno",
        [
            {
                "name": "turns",
                "kind": "integer_list",
                "required": True,
                "minimum": 1,
                "maximum": 6,
            }
        ],
    ),
]


def upgrade() -> None:
    effect_types = op.create_table(
        "location_effect_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.UniqueConstraint("code", name="uq_location_effect_types_code"),
        sa.UniqueConstraint("name", name="uq_location_effect_types_name"),
    )
    op.bulk_insert(
        effect_types,
        [{"code": c, "name": n, "parameters": p} for c, n, p in EFFECT_TYPES],
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("card_limit", sa.Integer(), nullable=False),
        sa.Column("extra_energy_mode", sa.String(10), nullable=False),
        sa.Column("extra_energy_amount", sa.Integer(), nullable=False),
        sa.Column(
            "effect_type_id",
            sa.Integer(),
            sa.ForeignKey("location_effect_types.id", name="fk_locations_effect_types"),
            nullable=True,
        ),
        sa.Column("effect_parameters", sa.JSON(), nullable=False),
        sa.Column("image_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "thumbnail_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("thumbnail_last_error", sa.String(500), nullable=True),
        sa.Column("thumbnail_claimed_until", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "card_limit BETWEEN 0 AND 5", name="ck_locations_card_limit"
        ),
        sa.CheckConstraint(
            "extra_energy_amount >= 0 AND ("
            "(extra_energy_mode = 'fixed' AND extra_energy_amount <= 3) OR "
            "(extra_energy_mode = 'per_card' AND extra_energy_amount <= 2))",
            name="ck_locations_extra_energy",
        ),
    )
    op.create_index("ix_locations_status", "locations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_locations_status", table_name="locations")
    op.drop_table("locations")
    op.drop_table("location_effect_types")
