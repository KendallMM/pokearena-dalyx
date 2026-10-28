import asyncio
import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.models.carta_model import CardCodeCounter, IdempotencyKey, ImageJob
from tests.api import add_ability, all_cards, post_card
from tests.helpers import auth, card_fields, card_image, make_image, make_token, pad_to


def err(response):
    return response.json()["error"]


async def test_success_creates_card_ready_with_thumbnail(client, container):
    response = await post_card(client)
    assert response.status_code == 202
    body = response.json()
    assert body == {
        "code": "PKA-ELE-001",
        "status": "PENDING_IMAGE",
        "status_url": "/admin/cartas/PKA-ELE-001/estado",
    }
    # El BackgroundTask ya corrió al terminar la respuesta.
    status = await client.get(body["status_url"], headers=auth())
    assert status.status_code == 200
    assert status.json() == {
        "code": "PKA-ELE-001",
        "status": "READY",
        "image_processing": "DONE",
        "ability": {"code": "HAB-000", "affected_type": None},
    }
    [card] = await all_cards(container)
    assert (card.name, card.cost, card.power) == ("Pikachu", 3, 5)
    assert (card.card_type, card.rarity, card.status) == ("Eléctrico", "Común", "READY")
    doc = await container.card_images.get(card.image_ref)
    assert doc["status"] == "ATTACHED" and "temporary_expires_at" not in doc
    assert Image.open(io.BytesIO(doc["original"])).size == (600, 840)
    thumb = Image.open(io.BytesIO(doc["thumbnail"]))
    assert thumb.size == (200, 280)


async def test_stays_pending_until_processed(client, container, no_background):
    code = (await post_card(client)).json()["code"]
    s = (await client.get(f"/admin/cartas/{code}/estado", headers=auth())).json()
    assert s["status"] == "PENDING_IMAGE" and s["image_processing"] == "PENDING"
    assert await container.image_processing.run_due_jobs() == 1
    s = (await client.get(f"/admin/cartas/{code}/estado", headers=auth())).json()
    assert s["status"] == "READY"


async def test_per_type_consecutive_codes_and_prefixes(client, no_background):
    expected = {
        "Fuego": "FUE",
        "Agua": "AGU",
        "Planta": "PLA",
        "Eléctrico": "ELE",
        "Psíquico": "PSI",
        "Lucha": "LUC",
    }
    for card_type, prefix in expected.items():
        for n in (1, 2):
            r = await post_card(client, type=card_type)
            assert r.json()["code"] == f"PKA-{prefix}-{n:03d}"


async def test_code_grows_to_four_digits_after_999(client, container, no_background):
    async with container.session_factory() as s, s.begin():
        counter = await s.get(CardCodeCounter, "Fuego")
        counter.last_number = 998
    assert (await post_card(client, type="Fuego")).json()["code"] == "PKA-FUE-999"
    assert (await post_card(client, type="Fuego")).json()["code"] == "PKA-FUE-1000"


@pytest.mark.parametrize("cost,power", [(0, -20), (10, 20)])
async def test_boundaries_accepted(client, no_background, cost, power):
    r = await post_card(client, cost=str(cost), power=str(power))
    assert r.status_code == 202


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"name": None}, "name"),
        ({"name": "  "}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"cost": None}, "cost"),
        ({"cost": "-1"}, "cost"),
        ({"cost": "11"}, "cost"),
        ({"cost": "abc"}, "cost"),
        ({"cost": "2.5"}, "cost"),
        ({"power": None}, "power"),
        ({"power": "21"}, "power"),
        ({"power": "-21"}, "power"),
        ({"type": None}, "type"),
        ({"type": "Hielo"}, "type"),
        ({"rarity": None}, "rarity"),
        ({"rarity": "Mítica"}, "rarity"),
        ({"ability": None}, "ability"),
        ({"ability": ""}, "ability"),
        ({"ability": "HAB-999"}, "ability"),
    ],
)
async def test_invalid_fields_are_400_and_create_nothing(
    client, container, overrides, field
):
    response = await post_card(client, **overrides)
    assert response.status_code == 400, response.text
    assert err(response)["field"] == field
    assert await all_cards(container) == []
    async with container.session_factory() as s:
        counters = {
            c.card_type: c.last_number for c in await s.scalars(select(CardCodeCounter))
        }
        assert set(counters.values()) == {0}
        assert await s.scalar(select(func.count()).select_from(IdempotencyKey)) == 0
        assert await s.scalar(select(func.count()).select_from(ImageJob)) == 0


async def test_unknown_ability_error_code(client):
    r = await post_card(client, ability="HAB-404")
    assert err(r)["code"] == "invalid_ability"
    r = await post_card(client, ability=None)
    assert err(r)["code"] == "invalid_ability"


async def test_ability_from_catalog_is_used(client, container, no_background):
    await add_ability(
        container, "HAB-010", effect_type="Modificar costo", affected_type="Agua"
    )
    r = await post_card(client, ability="HAB-010")
    assert r.status_code == 202
    s = (
        await client.get(f"/admin/cartas/{r.json()['code']}/estado", headers=auth())
    ).json()
    assert s["ability"] == {"code": "HAB-010", "affected_type": "Agua"}


@pytest.mark.parametrize(
    "image,requirement",
    [
        pytest.param(None, "required", id="sin-imagen"),
        pytest.param(b"", "empty", id="vacia"),
        pytest.param(b"esto no es una imagen", "format", id="texto"),
        pytest.param(make_image(600, 840, "GIF", "P"), "format", id="gif"),
        pytest.param(make_image(600, 840, "BMP"), "format", id="bmp"),
        pytest.param(make_image(599, 840), "min_resolution", id="ancho-599"),
        pytest.param(make_image(600, 839), "min_resolution", id="alto-839"),
        pytest.param(make_image(300, 420), "min_resolution", id="pequena"),
        pytest.param(make_image(600, 841), "ratio", id="ratio-600x841"),
        pytest.param(make_image(1400, 1000), "ratio", id="horizontal"),
        pytest.param(
            make_image(1000, 1400)[: len(make_image(1000, 1400)) // 2],
            "corrupt",
            id="truncada",
        ),
    ],
)
async def test_invalid_images(client, container, image, requirement):
    r = await post_card(client, image=image)
    assert r.status_code == 400, r.text
    assert err(r)["code"] == "invalid_image"
    assert err(r)["field"] == "image"
    assert err(r)["details"]["requirement"] == requirement
    assert await all_cards(container) == []
    assert await container.card_images._collection.count_documents({}) == 0


async def test_png_declared_as_jpeg_is_judged_by_real_content(client, no_background):
    files = {"image": ("x.jpg", card_image("PNG"), "image/jpeg")}
    r = await client.post(
        "/admin/cartas",
        data=card_fields(),
        files=files,
        headers={**auth(), "Idempotency-Key": "k1"},
    )
    assert r.status_code == 202


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
async def test_allowed_formats_and_thumbnail_keeps_format(client, container, fmt):
    r = await post_card(client, image=make_image(600, 840, fmt))
    assert r.status_code == 202
    [card] = await all_cards(container)
    assert card.status == "READY"
    doc = await container.card_images.get(card.image_ref)
    assert Image.open(io.BytesIO(doc["thumbnail"])).format == fmt


async def test_image_size_limit_exact(client, no_background):
    five_mib = 5 * 1024 * 1024
    ok = await post_card(client, image=pad_to(card_image(), five_mib))
    assert ok.status_code == 202
    too_big = await post_card(client, image=pad_to(card_image(), five_mib + 1))
    assert too_big.status_code == 400
    assert err(too_big)["details"]["requirement"] == "max_size"


async def test_huge_dimensions_rejected_without_decoding(client):
    from PIL import Image as PILImage

    buffer = io.BytesIO()
    PILImage.new("1", (6000, 8400)).save(buffer, "PNG")  # 50 Mpx, pesa poco
    r = await post_card(client, image=buffer.getvalue())
    assert err(r)["details"]["requirement"] == "dimensions_too_large"


# ---- Idempotencia ---------------------------------------------------------


async def test_replay_returns_original_with_200_and_no_duplicate(
    client, container, no_background
):
    first = await post_card(client, key="abc-1")
    again = await post_card(client, key="abc-1")
    assert (first.status_code, again.status_code) == (202, 200)
    assert first.json() == again.json()
    assert len(await all_cards(container)) == 1


async def test_same_key_other_payload_is_409(client, container, no_background):
    await post_card(client, key="abc-2")
    for r in (
        await post_card(client, key="abc-2", name="Otro"),
        await post_card(client, key="abc-2", image=make_image(1200, 1680)),
    ):
        assert r.status_code == 409
        assert err(r)["code"] == "idempotency_key_reused"
    assert len(await all_cards(container)) == 1


@pytest.mark.parametrize("key", [None, "", "   ", "con espacios", "x" * 129, "a/b"])
async def test_missing_or_bad_key_is_400(client, container, key):
    r = await post_card(client, key=key)
    assert r.status_code == 400
    assert err(r)["code"] == "idempotency_key_required"
    assert await all_cards(container) == []


async def test_key_scoped_per_user_and_endpoint(client, container, no_background):
    a = await post_card(client, key="same", headers=auth(make_token(sub="u1")))
    b = await post_card(client, key="same", headers=auth(make_token(sub="u2")))
    assert (a.status_code, b.status_code) == (202, 202)
    assert a.json()["code"] != b.json()["code"]
    from tests.api import post_location

    c = await post_location(client, key="same", headers=auth(make_token(sub="u1")))
    assert c.status_code == 202


async def test_failed_request_does_not_burn_the_key(client, no_background):
    bad = await post_card(client, key="retry-me", cost="99")
    assert bad.status_code == 400
    good = await post_card(client, key="retry-me")
    assert good.status_code == 202


async def test_concurrent_same_key_creates_one_card(
    client, container, is_mysql, no_background
):
    if not is_mysql:
        pytest.skip("requiere MySQL/MariaDB real (bloqueos de fila)")
    results = await asyncio.gather(*[post_card(client, key="race") for _ in range(8)])
    assert sorted(r.status_code for r in results).count(202) == 1
    assert {r.status_code for r in results} <= {200, 202}
    assert len({r.json()["code"] for r in results}) == 1
    assert len(await all_cards(container)) == 1


async def test_concurrent_distinct_requests_get_unique_consecutive_codes(
    client, container, is_mysql, no_background
):
    if not is_mysql:
        pytest.skip("requiere MySQL/MariaDB real (bloqueos de fila)")
    results = await asyncio.gather(
        *[post_card(client, name=f"C{i}") for i in range(20)]
    )
    assert all(r.status_code == 202 for r in results)
    codes = sorted(r.json()["code"] for r in results)
    assert codes == [f"PKA-ELE-{i:03d}" for i in range(1, 21)]


# ---- Reversa y evolución --------------------------------------------------


async def test_failed_transaction_rolls_back_counter_and_cleans_temp_image(
    client, container, monkeypatch
):
    from app.routers import cartas as card_service

    def boom(*_a, **_k):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(card_service, "format_card_code", boom)
    with pytest.raises(RuntimeError):
        await post_card(client)
    assert await container.card_images._collection.count_documents({}) == 0
    async with container.session_factory() as s:
        assert (
            await s.scalar(
                select(CardCodeCounter.last_number).where(
                    CardCodeCounter.card_type == "Eléctrico"
                )
            )
            == 0
        )
        assert await s.scalar(select(func.count()).select_from(IdempotencyKey)) == 0


async def test_mongo_down_gives_503_and_nothing_in_mysql(
    client, container, monkeypatch
):
    from pymongo.errors import ServerSelectionTimeoutError

    async def fail(*_a, **_k):
        raise ServerSelectionTimeoutError("caído")

    monkeypatch.setattr(container.card_images, "save_temporary", fail)
    r = await post_card(client)
    assert r.status_code == 503 and err(r)["code"] == "storage_unavailable"
    assert await all_cards(container) == []


async def test_evolution_to_itself_is_rejected(client, container):
    await add_ability(
        container,
        "HAB-020",
        effect_type="Evolucionar",
        parameters={"target_card_code": "PKA-ELE-001"},
    )
    r = await post_card(client, ability="HAB-020")  # recibirá PKA-ELE-001
    assert r.status_code == 400 and err(r)["code"] == "invalid_evolution"
    assert await all_cards(container) == []
    assert await container.card_images._collection.count_documents({}) == 0
    # el consecutivo no se gastó
    ok = await post_card(client)
    assert ok.json()["code"] == "PKA-ELE-001"


async def test_evolution_cycle_is_rejected(client, container, no_background):
    await add_ability(
        container,
        "HAB-021",
        effect_type="Evolucionar",
        parameters={"target_card_code": "PKA-ELE-002"},
    )
    await add_ability(
        container,
        "HAB-022",
        effect_type="Evolucionar",
        parameters={"target_card_code": "PKA-ELE-001"},
    )
    first = await post_card(client, ability="HAB-021")  # 001 -> 002 (aún no existe)
    assert first.status_code == 202
    second = await post_card(client, ability="HAB-022")  # 002 -> 001 cierra el ciclo
    assert second.status_code == 400 and err(second)["code"] == "invalid_evolution"
    assert len(await all_cards(container)) == 1


async def test_valid_evolution_chain_is_accepted(client, container, no_background):
    await add_ability(
        container,
        "HAB-023",
        effect_type="Evolucionar",
        parameters={"target_card_code": "PKA-ELE-001"},
    )
    assert (await post_card(client)).status_code == 202
    assert (await post_card(client, ability="HAB-023")).status_code == 202


async def test_status_and_image_404s(client):
    for path in (
        "/admin/cartas/PKA-ELE-999/estado",
        "/admin/cartas/PKA-ELE-999/imagen",
    ):
        r = await client.get(path, headers=auth())
        assert r.status_code == 404 and err(r)["code"] == "not_found"


async def test_image_endpoint_serves_large_and_small(client, container):
    code = (await post_card(client)).json()["code"]
    large = await client.get(f"/admin/cartas/{code}/imagen", headers=auth())
    assert large.status_code == 200 and large.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(large.content)).size == (600, 840)
    small = await client.get(
        f"/admin/cartas/{code}/imagen?version=small", headers=auth()
    )
    assert Image.open(io.BytesIO(small.content)).size == (200, 280)
    bad = await client.get(f"/admin/cartas/{code}/imagen?version=huge", headers=auth())
    assert bad.status_code == 400
    assert (await client.get(f"/admin/cartas/{code}/imagen")).status_code == 401


async def test_unknown_route_uses_envelope(client):
    r = await client.get("/nada")
    assert r.status_code == 404 and err(r)["code"] == "not_found"
