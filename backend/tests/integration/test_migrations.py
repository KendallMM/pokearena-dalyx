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


def test_location_catalog_is_seeded_and_locations_table_enforces_ranges(
    database_url,
) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        codes = connection.execute(
            text("SELECT code FROM location_effect_types ORDER BY id")
        ).scalars()
        assert list(codes) == ["type_bonus", "cost_modifier", "turn_restriction"]

    insert = text(
        "INSERT INTO locations (name, description, card_limit, extra_energy_mode, "
        "extra_energy_amount, effect_parameters, image_id, status) VALUES "
        "('a', 'b', :limit, :mode, :amount, '{}', 'x', 'pending_thumbnail')"
    )
    valid = {"limit": 5, "mode": "per_card", "amount": 2}
    with engine.begin() as connection:
        connection.execute(insert, valid)
    for bad in [
        {**valid, "limit": 6},
        {**valid, "limit": -1},
        {**valid, "amount": 3},  # el máximo por carta es 2
        {"limit": 1, "mode": "fixed", "amount": 4},  # el máximo fijo es 3
        {**valid, "mode": "weekly"},
    ]:
        try:
            with engine.begin() as connection:
                connection.execute(insert, bad)
        except IntegrityError:
            continue
        raise AssertionError(f"La base aceptó un valor inválido: {bad}")
