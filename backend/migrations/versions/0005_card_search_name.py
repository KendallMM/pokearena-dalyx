"""Nombre de búsqueda de las cartas (sin tildes ni mayúsculas).

Revision ID: 0005
Revises: 0004
"""

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _normalize(text: str) -> str:
    # Misma regla que app.business.shared.text.normalize_for_search. Se repite aquí
    # para que la migración no cambie si el código de la aplicación cambia.
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.casefold().split())


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "search_name", sa.String(100), nullable=False, server_default=sa.text("''")
        ),
    )
    # Las cartas que ya existen reciben su nombre de búsqueda.
    connection = op.get_bind()
    cards = sa.table(
        "cards", sa.column("id", sa.Integer), sa.column("search_name", sa.String)
    )
    rows = connection.execute(sa.text("SELECT id, name FROM cards")).all()
    for card_id, name in rows:
        connection.execute(
            cards.update()
            .where(cards.c.id == card_id)
            .values(search_name=_normalize(name))
        )


def downgrade() -> None:
    with op.batch_alter_table("cards") as batch:
        batch.drop_column("search_name")
