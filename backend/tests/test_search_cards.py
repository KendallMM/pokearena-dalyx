import pytest
from sqlalchemy import event

from app.database import decode_cursor, encode_cursor
from tests.api import add_ability, insert_cards, post_card
from tests.helpers import CURSOR_SECRET, auth, make_token


def err(r):
    return r.json()["error"]


async def search(client, **params):
    return await client.get("/admin/cartas", params=params, headers=auth())


async def seed_variety(container):
    """Seis cartas distintas para probar filtros."""
    from app.engine.ability_engine import normalize_text
    from app.models.carta_model import Card
    from tests.api import ability_id

    await add_ability(
        container, "HAB-001", trigger_type="Continuo", effect_type="Mover"
    )
    await add_ability(
        container, "HAB-002", trigger_type="Al revelarse", effect_type="Modificar poder"
    )
    a0 = await ability_id(container, "HAB-000")
    a1 = await ability_id(container, "HAB-001")
    a2 = await ability_id(container, "HAB-002")
    rows = [
        ("PKA-ELE-001", "Pikachu", 3, 5, "Eléctrico", "Común", a0),
        ("PKA-ELE-002", "Raichu", 6, 12, "Eléctrico", "Rara", a1),
        ("PKA-FUE-001", "Charmander", 2, 4, "Fuego", "Común", a2),
        ("PKA-FUE-002", "Éspeon 100%", 5, -3, "Fuego", "Legendaria", a1),
        ("PKA-AGU-001", "Squirtle_x", 0, 0, "Agua", "Poco común", a0),
        ("PKA-PLA-001", "Bulbasaur", 10, 20, "Planta", "Poco común", a2),
    ]
    async with container.session_factory() as s, s.begin():
        for code, name, cost, power, t, rar, aid in rows:
            s.add(
                Card(
                    code=code,
                    name=name,
                    name_search=normalize_text(name),
                    cost=cost,
                    power=power,
                    card_type=t,
                    rarity=rar,
                    ability_id=aid,
                    status="READY",
                    image_ref=code,
                    created_by="x",
                )
            )


def codes(response):
    return [i["code"] for i in response.json()["items"]]


async def test_empty_database_returns_empty_page(client):
    r = await search(client)
    assert r.status_code == 200
    assert r.json() == {"items": [], "next_cursor": None, "has_more": False}


@pytest.mark.parametrize(
    "params,expected",
    [
        (
            {},
            [
                "PKA-ELE-001",
                "PKA-ELE-002",
                "PKA-FUE-001",
                "PKA-FUE-002",
                "PKA-AGU-001",
                "PKA-PLA-001",
            ],
        ),
        ({"code": "PKA-FUE-001"}, ["PKA-FUE-001"]),
        ({"code": "pka-fue-001"}, ["PKA-FUE-001"]),
        ({"name": "pika"}, ["PKA-ELE-001"]),
        ({"name": "PIKACHU"}, ["PKA-ELE-001"]),
        ({"name": "espeon"}, ["PKA-FUE-002"]),  # sin tilde encuentra "Éspeon"
        ({"name": "éspeon"}, ["PKA-FUE-002"]),
        ({"name": "chu"}, ["PKA-ELE-001", "PKA-ELE-002"]),
        ({"name": "%"}, ["PKA-FUE-002"]),  # comodín literal
        ({"name": "_"}, ["PKA-AGU-001"]),  # comodín literal
        ({"name": "a_"}, []),
        ({"name": "zzz"}, []),
        (
            {"name": "   "},
            [
                "PKA-ELE-001",
                "PKA-ELE-002",
                "PKA-FUE-001",
                "PKA-FUE-002",
                "PKA-AGU-001",
                "PKA-PLA-001",
            ],
        ),
        ({"cost": "3"}, ["PKA-ELE-001"]),
        ({"cost_min": "5"}, ["PKA-ELE-002", "PKA-FUE-002", "PKA-PLA-001"]),
        ({"cost_max": "2"}, ["PKA-FUE-001", "PKA-AGU-001"]),
        (
            {"cost_min": "2", "cost_max": "5"},
            ["PKA-ELE-001", "PKA-FUE-001", "PKA-FUE-002"],
        ),
        ({"power": "0"}, ["PKA-AGU-001"]),
        ({"power_min": "-3", "power_max": "0"}, ["PKA-FUE-002", "PKA-AGU-001"]),
        ({"power_min": "20"}, ["PKA-PLA-001"]),
        ({"type": "Fuego"}, ["PKA-FUE-001", "PKA-FUE-002"]),
        ({"rarity": "Poco común"}, ["PKA-AGU-001", "PKA-PLA-001"]),
        ({"ability_code": "HAB-001"}, ["PKA-ELE-002", "PKA-FUE-002"]),
        ({"ability_trigger": "Continuo"}, ["PKA-ELE-002", "PKA-FUE-002"]),
        ({"ability_effect": "Modificar poder"}, ["PKA-FUE-001", "PKA-PLA-001"]),
        ({"ability_trigger": "Al revelarse", "ability_effect": "Mover"}, []),
        ({"type": "Fuego", "rarity": "Común"}, ["PKA-FUE-001"]),
        ({"type": "Eléctrico", "cost_min": "4", "name": "rai"}, ["PKA-ELE-002"]),
        ({"type": "Agua", "rarity": "Rara"}, []),
        (
            {"type": ""},
            [
                "PKA-ELE-001",
                "PKA-ELE-002",
                "PKA-FUE-001",
                "PKA-FUE-002",
                "PKA-AGU-001",
                "PKA-PLA-001",
            ],
        ),
        ({"code": "PKA-ELE-777"}, []),  # bien formado pero inexistente -> vacío
    ],
)
async def test_filters(client, container, params, expected):
    await seed_variety(container)
    r = await search(client, **params)
    assert r.status_code == 200, r.text
    assert codes(r) == expected
    assert r.json()["has_more"] is False and r.json()["next_cursor"] is None


@pytest.mark.parametrize(
    "params,field",
    [
        ({"code": "XYZ"}, "code"),
        ({"code": "PKA-ELE-1"}, "code"),
        ({"cost": "11"}, "cost"),
        ({"cost": "x"}, "cost"),
        ({"cost_min": "-1"}, "cost_min"),
        ({"cost_min": "6", "cost_max": "2"}, "cost_min"),
        ({"cost": "3", "cost_min": "1"}, "cost"),
        ({"power": "21"}, "power"),
        ({"power_min": "5", "power_max": "-5"}, "power_min"),
        ({"type": "Hielo"}, "type"),
        ({"rarity": "Mítica"}, "rarity"),
        ({"ability_code": "ABC"}, "ability_code"),
        ({"ability_trigger": "Nunca"}, "ability_trigger"),
        ({"ability_effect": "Nada"}, "ability_effect"),
        ({"limit": "0"}, "limit"),
        ({"limit": "51"}, "limit"),
        ({"limit": "-3"}, "limit"),
        ({"limit": "abc"}, "limit"),
        ({"name": "x" * 101}, "name"),
    ],
)
async def test_invalid_criteria_are_400(client, params, field):
    r = await search(client, **params)
    assert r.status_code == 400, r.text
    assert err(r)["code"] == "invalid_field" and err(r)["field"] == field


async def test_item_shape_and_image_links(client, container, no_background):
    await post_card(client)
    items = (await search(client)).json()["items"]
    assert (
        items[0]["status"] == "PENDING_IMAGE" and items[0]["image"] is None
    )  # incluye pendientes
    await container.image_processing.run_due_jobs()
    [item] = (await search(client)).json()["items"]
    assert item == {
        "code": "PKA-ELE-001",
        "name": "Pikachu",
        "cost": 3,
        "power": 5,
        "type": "Eléctrico",
        "rarity": "Común",
        "status": "READY",
        "ability": {
            "code": "HAB-000",
            "name": "Sin Habilidad",
            "trigger_type": None,
            "condition_type": None,
            "effect_type": None,
            "target_type": None,
            "affected_type": None,
            "parameters": {},
        },
        "image": {
            "large": "/admin/cartas/PKA-ELE-001/imagen?version=large",
            "small": "/admin/cartas/PKA-ELE-001/imagen?version=small",
        },
    }


async def test_pagination_120_cards_no_duplicates_or_gaps(client, container):
    await insert_cards(container, 120)
    seen, cursor, pages = [], None, 0
    while True:
        params = {"cursor": cursor} if cursor else {}
        body = (await search(client, **params)).json()
        pages += 1
        seen += [i["code"] for i in body["items"]]
        assert body["has_more"] == (body["next_cursor"] is not None)
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert seen == [f"PKA-FUE-{i:03d}" for i in range(1, 121)]


@pytest.mark.parametrize("limit,pages", [(1, 6), (7, 1), (3, 2)])
async def test_custom_limit(client, container, limit, pages):
    await seed_variety(container)
    body = (await search(client, limit=limit)).json()
    assert len(body["items"]) == min(limit, 6)
    count = 1
    while body["next_cursor"]:
        body = (await search(client, cursor=body["next_cursor"])).json()
        assert len(body["items"]) <= limit
        count += 1
    assert count == min(pages, 6)


async def test_exact_multiple_of_limit_has_no_phantom_page(client, container):
    await insert_cards(container, 50)
    body = (await search(client)).json()
    assert len(body["items"]) == 50
    assert body["has_more"] is False and body["next_cursor"] is None


async def test_cursor_keeps_filters_and_ignores_new_cards(client, container):
    await insert_cards(container, 7)
    first = (
        await search(client, limit=3, name="carta 1")
    ).json()  # "Carta 1" únicamente
    assert [i["code"] for i in first["items"]] == ["PKA-FUE-001"]
    first = (await search(client, limit=3, cost_min=0)).json()
    assert len(first["items"]) == 3
    # llegan cartas nuevas durante el recorrido
    await insert_cards_after(container, start=8, count=5)
    seen = [i["code"] for i in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = (await search(client, cursor=cursor)).json()
        seen += [i["code"] for i in page["items"]]
        cursor = page["next_cursor"]
    assert seen == [
        f"PKA-FUE-{i:03d}" for i in range(1, 8)
    ]  # sin duplicados ni las nuevas


async def insert_cards_after(container, start, count):
    from app.engine.ability_engine import normalize_text
    from app.models.carta_model import Card
    from tests.api import ability_id

    aid = await ability_id(container)
    async with container.session_factory() as s, s.begin():
        for i in range(start, start + count):
            s.add(
                Card(
                    code=f"PKA-FUE-{i:03d}",
                    name=f"Carta {i}",
                    name_search=normalize_text(f"Carta {i}"),
                    cost=1,
                    power=1,
                    card_type="Fuego",
                    rarity="Común",
                    ability_id=aid,
                    status="READY",
                    image_ref=f"r{i}",
                    created_by="x",
                )
            )


async def test_cursor_preserves_filters_across_pages(client, container):
    await seed_variety(container)
    first = (await search(client, type="Fuego", limit=1)).json()
    assert codes_of(first) == ["PKA-FUE-001"] and first["has_more"]
    second = (await search(client, cursor=first["next_cursor"])).json()
    assert codes_of(second) == ["PKA-FUE-002"] and not second["has_more"]


def codes_of(body):
    return [i["code"] for i in body["items"]]


async def test_cursor_with_filters_is_400(client, container):
    await insert_cards(container, 3)
    cursor = (await search(client, limit=1)).json()["next_cursor"]
    for extra in ({"name": "a"}, {"type": "Fuego"}, {"cost": "1"}, {"rarity": "Rara"}):
        r = await search(client, cursor=cursor, **extra)
        assert r.status_code == 400 and err(r)["field"] == "cursor"
    # limit sí se puede cambiar con cursor
    assert (await search(client, cursor=cursor, limit=1)).status_code == 200
    # filtros vacíos junto al cursor no cuentan
    assert (await search(client, cursor=cursor, name="", type="")).status_code == 200


async def test_bad_cursors(client, container):
    await insert_cards(container, 3)
    good = (await search(client, limit=1)).json()["next_cursor"]
    body, sig = good.split(".")
    forged_payload = encode_cursor(
        {"c": {}, "m": 999, "l": 0, "s": 5}, "otra-clave-otra-clave-otra-clave-12"
    )
    tampered = body[:-2] + ("AA" if not body.endswith("AA") else "BB") + "." + sig
    for bad in (
        "garbage",
        "a.b",
        good + "x",
        tampered,
        forged_payload,
        ".",
        body,
        "é.é",
    ):
        r = await search(client, cursor=bad)
        assert r.status_code == 400, bad
        assert err(r)["code"] == "invalid_cursor" and err(r)["field"] == "cursor"
    # firmado con el secreto correcto pero con contenido absurdo
    for payload in (
        {},
        {"c": 1, "m": 1, "l": 0, "s": 5},
        {"c": {"nope": 1}, "m": 1, "l": 0, "s": 5},
        {"c": {}, "m": "x", "l": 0, "s": 5},
        {"c": {}, "m": 1, "l": 0},
        {"c": {}, "m": 1, "l": 0, "s": 99},
    ):
        r = await search(client, cursor=encode_cursor(payload, CURSOR_SECRET))
        assert r.status_code == 400 and err(r)["code"] == "invalid_cursor"


async def test_cursor_payload_roundtrip():
    token = encode_cursor({"a": 1}, CURSOR_SECRET)
    assert decode_cursor(token, CURSOR_SECRET) == {"a": 1}


async def test_page_uses_at_most_two_sql_statements(client, container):
    await insert_cards(container, 120)
    statements = []
    engine = container.session_factory.kw["bind"]

    def count(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith(("SELECT", "UPDATE", "INSERT")):
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", count)
    try:
        first = (await search(client)).json()
        assert len(statements) == 2  # máximo id + página (con habilidad incluida)
        statements.clear()
        await search(client, cursor=first["next_cursor"])
        assert len(statements) == 1  # el cursor ya trae el máximo id
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count)


async def test_search_requires_admin(client):
    assert (await client.get("/admin/cartas")).status_code == 401
    r = await client.get("/admin/cartas", headers=auth(make_token(role="user")))
    assert r.status_code == 403


async def test_ten_thousand_cards_traversal(client, container):
    await insert_cards(container, 10_000, card_type="Fuego")
    total, cursor, pages = 0, None, 0
    last = 0
    while True:
        body = (await search(client, **({"cursor": cursor} if cursor else {}))).json()
        pages += 1
        for item in body["items"]:
            number = int(item["code"].rsplit("-", 1)[1])
            assert number == last + 1
            last = number
        total += len(body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert (total, pages) == (10_000, 200)
