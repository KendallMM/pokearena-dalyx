"""Migraciones: suben, bajan y dejan los datos iniciales."""

from alembic import command
from sqlalchemy import create_engine, inspect

from tests.integration.conftest import alembic_config


def test_upgrade_creates_tables_and_downgrade_removes_them(database_url) -> None:
    config = alembic_config(database_url)
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert {"card_types", "rarities", "abilities"} <= tables

    command.downgrade(config, "base")
    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert not {"card_types", "rarities", "abilities"} & tables
