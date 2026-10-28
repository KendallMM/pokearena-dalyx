import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.models.ubicacion_model import GameLocation, GameLocationVersion
from tests.api import post_location
from tests.helpers import auth, make_image, make_token, pad_to


def err(r):
    return r.json()["error"]


async def versions(container):
    async with container.session_factory() as s:
        return list((await s.scalars(select(GameLocationVersion))).all())


async def test_success_basic_location(client, container):
    r = await post_location(client)
    assert r.status_code == 202
    body = r.json()
    assert body == {
        "id": 1,
        "version": 1,
        "status": "PENDING_IMAGE",
        "status_url": "/admin/ubicaciones/1/estado",
    }
    status = (await client.get(body["status_url"], headers=auth())).json()
    assert status == {
        "id": 1,
        "version": 1,
        "status": "READY",
        "image_processing": "DONE",
    }
    [v] = await versions(container)
    assert (v.name, v.card_limit, v.extra_energy_mode, v.extra_energy_amount) == (
        "Bosque Verde",
        4,
        "fixed",
        1,
    )
    assert v.effect_type is None and v.effect_parameters == {}
    doc = await container.location_images.get(v.image_ref)
    assert Image.open(io.BytesIO(doc["thumbnail"])).size == (320, 240)
    assert Image.open(io.BytesIO(doc["original"])).size == (800, 600)


@pytest.mark.parametrize(
    "extra,effect_type,params",
    [
        (
            {
                "effect_type": "type_bonus",
                "effect_card_type": "Fuego",
                "effect_amount": "-5",
            },
            "type_bonus",
            {"card_type": "Fuego", "amount": -5},
        ),
        (
            {
                "effect_type": "type_bonus",
                "effect_card_type": "Agua",
                "effect_amount": "5",
            },
            "type_bonus",
            {"card_type": "Agua", "amount": 5},
        ),
        (
            {"effect_type": "cost_modifier", "effect_amount": "2"},
            "cost_modifier",
            {"amount": 2, "card_type": None},
        ),
        (
            {
                "effect_type": "cost_modifier",
                "effect_amount": "-1",
                "effect_card_type": "Lucha",
            },
            "cost_modifier",
            {"amount": -1, "card_type": "Lucha"},
        ),
        (
            {"effect_type": "turn_restriction", "effect_restricted_turns": ["4", "2"]},
            "turn_restriction",
            {"turns": [2, 4]},
        ),
    ],
)
async def test_effects_are_stored(
    client, container, no_background, extra, effect_type, params
):
    r = await post_location(client, **extra)
    assert r.status_code == 202, r.text
    [v] = await versions(container)
    assert v.effect_type == effect_type and v.effect_parameters == params


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"name": None}, "name"),
        ({"description": None}, "description"),
        ({"description": "x" * 256}, "description"),
        ({"card_limit": None}, "card_limit"),
        ({"card_limit": "6"}, "card_limit"),
        ({"card_limit": "-1"}, "card_limit"),
        ({"card_limit": "x"}, "card_limit"),
        ({"extra_energy_mode": None}, "extra_energy_mode"),
        ({"extra_energy_mode": "otra"}, "extra_energy_mode"),
        ({"extra_energy_amount": "4"}, "extra_energy_amount"),
        (
            {"extra_energy_mode": "per_card", "extra_energy_amount": "3"},
            "extra_energy_amount",
        ),
        ({"effect_type": "type_bonus", "effect_amount": "1"}, "effect_card_type"),
        (
            {
                "effect_type": "type_bonus",
                "effect_card_type": "Fuego",
                "effect_amount": "6",
            },
            "effect_amount",
        ),
        ({"effect_type": "cost_modifier"}, "effect_amount"),
        ({"effect_type": "turn_restriction"}, "effect_restricted_turns"),
        (
            {"effect_type": "turn_restriction", "effect_restricted_turns": ["7"]},
            "effect_restricted_turns",
        ),
        (
            {"effect_type": "turn_restriction", "effect_restricted_turns": ["1", "1"]},
            "effect_restricted_turns",
        ),
        (
            {
                "effect_type": "turn_restriction",
                "effect_restricted_turns": ["1"],
                "effect_amount": "2",
            },
            "effect_amount",
        ),
        ({"effect_type": "bogus"}, "effect_type"),
        ({"effect_amount": "2"}, "effect_type"),
    ],
)
async def test_invalid_location_fields(client, container, overrides, field):
    r = await post_location(client, **overrides)
    assert r.status_code == 400, r.text
    assert err(r)["field"] == field
    assert await versions(container) == []
    async with container.session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(GameLocation)) == 0


@pytest.mark.parametrize(
    "image,requirement",
    [
        pytest.param(None, "required", id="sin-imagen"),
        pytest.param(b"basura", "format", id="basura"),
        pytest.param(make_image(799, 600), "min_resolution", id="799"),
        pytest.param(make_image(800, 599), "min_resolution", id="599"),
        pytest.param(make_image(800, 601), "ratio", id="ratio"),
        pytest.param(make_image(600, 800), "min_resolution", id="vertical-chica"),
        pytest.param(make_image(1000, 1200), "ratio", id="vertical-grande"),
    ],
)
async def test_invalid_location_images(client, container, image, requirement):
    r = await post_location(client, image=image)
    assert r.status_code == 400
    assert err(r)["code"] == "invalid_image"
    assert err(r)["details"]["requirement"] == requirement
    assert await versions(container) == []
    assert await container.location_images._collection.count_documents({}) == 0


async def test_card_sized_image_is_rejected_for_location(client):
    r = await post_location(client, image=make_image(600, 840))
    assert r.status_code == 400


async def test_size_limit(client, no_background):
    from tests.helpers import location_image

    five = 5 * 1024 * 1024
    assert (
        await post_location(client, image=pad_to(location_image(), five))
    ).status_code == 202
    r = await post_location(client, image=pad_to(location_image(), five + 1))
    assert err(r)["details"]["requirement"] == "max_size"


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
async def test_formats(client, fmt):
    assert (
        await post_location(client, image=make_image(800, 600, fmt))
    ).status_code == 202


async def test_idempotency_replay_conflict_and_missing(
    client, container, no_background
):
    a = await post_location(client, key="loc-1")
    b = await post_location(client, key="loc-1")
    assert (a.status_code, b.status_code) == (202, 200) and a.json() == b.json()
    assert len(await versions(container)) == 1
    c = await post_location(client, key="loc-1", name="Distinto")
    assert c.status_code == 409 and err(c)["code"] == "idempotency_key_reused"
    d = await post_location(client, key=None)
    assert d.status_code == 400 and err(d)["code"] == "idempotency_key_required"
    e = await post_location(client, key="otra", headers=auth(make_token(sub="u2")))
    assert e.status_code == 202


async def test_ids_increment_and_version_one(client, container, no_background):
    ids = [(await post_location(client)).json()["id"] for _ in range(3)]
    assert ids == [1, 2, 3]
    assert {v.version for v in await versions(container)} == {1}


async def test_status_404(client):
    r = await client.get("/admin/ubicaciones/99/estado", headers=auth())
    assert r.status_code == 404 and err(r)["code"] == "not_found"
    r = await client.get("/admin/ubicaciones/abc/estado", headers=auth())
    assert r.status_code == 400


async def test_failed_transaction_cleans_temp_image(client, container, monkeypatch):
    from app.routers import ubicaciones as svc

    async def boom(self):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(svc.GameLocationRepository, "add_location", boom)
    with pytest.raises(RuntimeError):
        await post_location(client)
    assert await container.location_images._collection.count_documents({}) == 0
    assert await versions(container) == []
