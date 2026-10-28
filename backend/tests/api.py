"""Atajos para llamar a la API desde las pruebas."""

import uuid

from sqlalchemy import select

from app.engine import ability_engine as catalog
from app.models.carta_model import Ability, Card
from tests.helpers import auth, card_fields, card_image, location_fields, location_image


async def post_card(
    client, fields=None, image="default", key="default", headers=None, **ov
):
    fields = card_fields(**ov) if fields is None else fields
    files = None
    if image == "default":
        image = card_image()
    if image is not None:
        files = {"image": ("carta.png", image, "image/png")}
    hdrs = dict(headers if headers is not None else auth())
    if key == "default":
        key = uuid.uuid4().hex
    if key is not None:
        hdrs["Idempotency-Key"] = key
    return await client.post("/admin/cartas", data=fields, files=files, headers=hdrs)


async def post_location(
    client, fields=None, image="default", key="default", headers=None, **ov
):
    fields = location_fields(**ov) if fields is None else fields
    files = None
    if image == "default":
        image = location_image()
    if image is not None:
        files = {"image": ("ub.png", image, "image/png")}
    hdrs = dict(headers if headers is not None else auth())
    if key == "default":
        key = uuid.uuid4().hex
    if key is not None:
        hdrs["Idempotency-Key"] = key
    return await client.post(
        "/admin/ubicaciones", data=fields, files=files, headers=hdrs
    )


async def add_ability(container, code, **kw):
    data = dict(
        name=f"Habilidad {code}",
        trigger_type="Al revelarse",
        condition_type=None,
        effect_type="Modificar poder",
        target_type="Carta",
        affected_type=None,
        parameters={},
    )
    data.update(kw)
    async with container.session_factory() as session, session.begin():
        ability = Ability(code=code, **data)
        session.add(ability)
        await session.flush()
        return ability.id


async def ability_id(container, code="HAB-000"):
    async with container.session_factory() as session:
        return await session.scalar(select(Ability.id).where(Ability.code == code))


async def insert_cards(container, count, **kw):
    """Inserta cartas directo en la base (para pruebas de búsqueda)."""
    from app.engine.ability_engine import normalize_text

    aid = await ability_id(container)
    async with container.session_factory() as session, session.begin():
        for i in range(1, count + 1):
            values = dict(
                code=f"PKA-FUE-{i:03d}",
                name=f"Carta {i}",
                cost=i % 11,
                power=(i % 41) - 20,
                card_type="Fuego",
                rarity="Común",
                ability_id=aid,
                status=catalog.STATUS_READY,
                image_ref=f"ref{i}",
                created_by="x",
            )
            values.update(kw)
            values["name_search"] = normalize_text(values["name"])
            session.add(Card(**values))


async def all_cards(container):
    async with container.session_factory() as session:
        return list((await session.scalars(select(Card).order_by(Card.id))).all())
