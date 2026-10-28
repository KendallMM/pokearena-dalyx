import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.models.carta_model import ImageJob, utc_now
from tests.api import all_cards, post_card, post_location
from tests.helpers import auth


async def jobs(container):
    async with container.session_factory() as s:
        return list((await s.scalars(select(ImageJob).order_by(ImageJob.id))).all())


async def card_status(client, code):
    return (await client.get(f"/admin/cartas/{code}/estado", headers=auth())).json()


@pytest.fixture
def broken_thumbnails(monkeypatch):
    state = {"fail": True, "calls": 0}
    from app import main as svc

    original = svc.make_thumbnail

    def flaky(data, size):
        state["calls"] += 1
        if state["fail"]:
            raise OSError("miniatura falló")
        return original(data, size)

    monkeypatch.setattr(svc, "make_thumbnail", flaky)
    return state


async def test_failure_goes_to_retry_then_recovers(
    client, container, no_background, broken_thumbnails
):
    code = (await post_card(client)).json()["code"]
    assert await container.image_processing.run_due_jobs() == 1
    s = await card_status(client, code)
    assert s["status"] == "RETRY_IMAGE" and s["image_processing"] == "RETRY"
    [job] = await jobs(container)
    assert job.attempts == 1 and "miniatura" in job.last_error
    doc = await container.card_images.get((await all_cards(container))[0].image_ref)
    assert doc["thumbnail"] is None  # nunca queda READY a medias
    broken_thumbnails["fail"] = False
    assert await container.image_processing.run_due_jobs() == 1
    s = await card_status(client, code)
    assert s["status"] == "READY" and s["image_processing"] == "DONE"
    assert (await jobs(container))[0].attempts == 2


async def test_gives_up_after_max_attempts(
    client, container, no_background, broken_thumbnails
):
    code = (await post_card(client)).json()["code"]
    for _ in range(5):
        await container.image_processing.run_due_jobs()
    [job] = await jobs(container)
    assert (
        job.status == "FAILED" and job.attempts == 3
    )  # image_max_attempts=3 en pruebas
    assert broken_thumbnails["calls"] == 3
    assert (await card_status(client, code))["status"] == "RETRY_IMAGE"
    assert await container.image_processing.run_due_jobs() == 0  # ya no se reintenta


async def test_retry_waits_for_backoff(
    client, container, no_background, broken_thumbnails
):
    await post_card(client)
    await container.image_processing.run_due_jobs()
    async with container.session_factory() as s, s.begin():
        await s.execute(
            update(ImageJob).values(next_attempt_at=utc_now() + timedelta(hours=1))
        )
    broken_thumbnails["fail"] = False
    assert await container.image_processing.run_due_jobs() == 0
    async with container.session_factory() as s, s.begin():
        await s.execute(
            update(ImageJob).values(next_attempt_at=utc_now() - timedelta(seconds=1))
        )
    assert await container.image_processing.run_due_jobs() == 1


async def test_stuck_processing_job_is_recovered_after_lock_expires(
    client, container, no_background
):
    code = (await post_card(client)).json()["code"]
    async with container.session_factory() as s, s.begin():  # un worker murió a medias
        await s.execute(
            update(ImageJob).values(
                status="PROCESSING",
                attempts=1,
                locked_until=utc_now() + timedelta(minutes=5),
            )
        )
    assert await container.image_processing.run_due_jobs() == 0  # aún bloqueado
    async with container.session_factory() as s, s.begin():
        await s.execute(
            update(ImageJob).values(locked_until=utc_now() - timedelta(seconds=1))
        )
    assert await container.image_processing.run_due_jobs() == 1
    assert (await card_status(client, code))["status"] == "READY"


async def test_job_is_processed_only_once(client, container, no_background):
    await post_card(client)
    [job] = await jobs(container)
    results = await asyncio.gather(
        *[container.image_processing.process_job(job.id) for _ in range(5)]
    )
    assert results.count(True) == 1
    assert (await jobs(container))[0].attempts == 1


async def test_missing_original_never_becomes_ready(client, container, no_background):
    code = (await post_card(client)).json()["code"]
    ref = (await all_cards(container))[0].image_ref
    await container.card_images.delete(ref)
    await container.image_processing.run_due_jobs()
    assert (await card_status(client, code))["status"] == "RETRY_IMAGE"


async def test_thumbnail_missing_after_save_is_not_ready(
    client, container, no_background, monkeypatch
):
    code = (await post_card(client)).json()["code"]

    async def lie(self, image_ref):
        return False

    monkeypatch.setattr(type(container.card_images), "has_both", lie)
    await container.image_processing.run_due_jobs()
    assert (await card_status(client, code))["status"] == "RETRY_IMAGE"


async def test_location_job_processed_and_retried(
    client, container, no_background, broken_thumbnails
):
    r = await post_location(client)
    await container.image_processing.run_due_jobs()
    s = (
        await client.get(f"/admin/ubicaciones/{r.json()['id']}/estado", headers=auth())
    ).json()
    assert s["status"] == "RETRY_IMAGE"
    broken_thumbnails["fail"] = False
    await container.image_processing.run_due_jobs()
    s = (
        await client.get(f"/admin/ubicaciones/{r.json()['id']}/estado", headers=auth())
    ).json()
    assert s["status"] == "READY"


async def test_poller_loop_picks_up_pending_jobs(client, container, no_background):
    from app.main import run_image_worker

    code = (await post_card(client)).json()["code"]
    stop = asyncio.Event()
    task = asyncio.create_task(run_image_worker(container.image_processing, 0.05, stop))
    for _ in range(100):
        if (await card_status(client, code))["status"] == "READY":
            break
        await asyncio.sleep(0.05)
    stop.set()
    await task
    assert (await card_status(client, code))["status"] == "READY"


async def test_poller_survives_errors(container, monkeypatch):
    from app.main import run_image_worker

    calls = {"n": 0}

    async def explode():
        calls["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(container.image_processing, "run_due_jobs", explode)
    stop = asyncio.Event()
    task = asyncio.create_task(run_image_worker(container.image_processing, 0.01, stop))
    await asyncio.sleep(0.15)
    stop.set()
    await task
    assert calls["n"] >= 2


async def test_temporary_image_expires_if_never_attached(container):
    await container.card_images.save_temporary("abc", "image/png", b"x", 60)
    doc = await container.card_images.get("abc")
    assert doc["status"] == "TEMPORARY" and doc["temporary_expires_at"] > utc_now()
    await container.card_images.attach("abc")
    doc = await container.card_images.get("abc")
    assert doc["status"] == "ATTACHED" and "temporary_expires_at" not in doc
