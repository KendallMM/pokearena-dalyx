"""POST /admin/ubicaciones con la lógica real y dobles en la persistencia."""

import json

from tests.unit.image_helpers import make_image

FORM = {
    "name": "Volcán",
    "description": "Un volcán activo",
    "card_limit": "3",
    "extra_energy_mode": "fixed",
    "extra_energy_amount": "1",
    "effect_type": "type_bonus",
    "effect_parameters": json.dumps({"card_type": "FUE", "amount": 2}),
}


def _post(client, token, form=None, image=..., key="op-1", **extra_headers):
    headers = {"Authorization": f"Bearer {token}", **extra_headers}
    if key is not None:
        headers["Idempotency-Key"] = key
    files = None
    if image is ...:
        image = make_image(800, 600)
    if image is not None:
        files = {"image": ("ubicacion.png", image, "image/png")}
    return client.post(
        "/admin/ubicaciones",
        data=form if form is not None else FORM,
        files=files,
        headers=headers,
    )


def test_without_credentials_returns_401(client) -> None:
    response = client.post("/admin/ubicaciones", data=FORM)
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_without_admin_role_returns_403_and_saves_nothing(
    client, make_token, image_store
) -> None:
    response = _post(client, make_token(role="player"))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert image_store.saved == {}


def test_creates_location_and_returns_202(client, make_token) -> None:
    response = _post(client, make_token())
    assert response.status_code == 202
    assert response.json() == {
        "id": 1,
        "status": "pending_thumbnail",
        "message": "Ubicación en proceso",
    }


def test_creates_location_without_effect(client, make_token, location_repository):
    form = {k: v for k, v in FORM.items() if not k.startswith("effect")}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 202
    assert location_repository.added[0].effect_type is None


def test_creates_location_with_per_card_energy(client, make_token, location_repository):
    form = {**FORM, "extra_energy_mode": "per_card", "extra_energy_amount": "2"}
    assert _post(client, make_token(), form=form).status_code == 202
    assert location_repository.added[0].extra_energy_amount == 2


def test_repeating_the_operation_does_not_create_another_location(
    client, make_token, location_repository, image_store
) -> None:
    token = make_token()
    first = _post(client, token)
    second = _post(client, token)
    assert second.status_code == 202
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert len(location_repository.added) == 1
    assert len(image_store.saved) == 1


def test_missing_operation_id_returns_400(client, make_token) -> None:
    response = _post(client, make_token(), key=None)
    assert response.status_code == 400
    assert response.json()["field"] == "Idempotency-Key"


def test_invalid_values_return_400_naming_the_field(
    client, make_token, image_store, location_repository
) -> None:
    cases = {
        "name": {**FORM, "name": " "},
        "description": {**FORM, "description": ""},
        "card_limit": {**FORM, "card_limit": "6"},
        "extra_energy_mode": {**FORM, "extra_energy_mode": "weekly"},
        "extra_energy_amount": {**FORM, "extra_energy_amount": "4"},
        "effect_type": {**FORM, "effect_type": "teleport"},
        "effect_parameters.amount": {
            **FORM,
            "effect_parameters": json.dumps({"card_type": "FUE", "amount": 9}),
        },
        "effect_parameters.card_type": {
            **FORM,
            "effect_parameters": json.dumps({"card_type": "XXX", "amount": 1}),
        },
        "effect_parameters": {**FORM, "effect_parameters": "no es json"},
    }
    for index, (field, form) in enumerate(cases.items()):
        response = _post(client, make_token(), form=form, key=f"k{index}")
        assert response.status_code == 400, field
        assert response.json()["field"] == field
    assert image_store.saved == {} and location_repository.added == []


def test_effect_parameters_must_be_a_json_object(client, make_token) -> None:
    form = {**FORM, "effect_parameters": "[1, 2]"}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 400
    assert response.json()["field"] == "effect_parameters"


def test_parameters_without_an_effect_are_rejected(client, make_token) -> None:
    form = {k: v for k, v in FORM.items() if k != "effect_type"}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 400
    assert response.json()["field"] == "effect_parameters"


def test_non_numeric_limit_returns_400_naming_the_field(client, make_token) -> None:
    response = _post(client, make_token(), form={**FORM, "card_limit": "abc"})
    assert response.status_code == 400
    assert response.json()["field"] == "card_limit"


def test_missing_energy_fields_return_400(client, make_token) -> None:
    form = {k: v for k, v in FORM.items() if k != "extra_energy_mode"}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 400
    assert response.json()["field"] == "extra_energy_mode"


def test_missing_image_returns_400(client, make_token) -> None:
    response = _post(client, make_token(), image=None)
    assert response.status_code == 400
    assert response.json()["field"] == "image"


def test_invalid_images_return_400_and_location_is_not_saved(
    client, make_token, location_repository, image_store
) -> None:
    bad_images = {
        "formato": make_image(800, 600, "GIF"),
        "proporción": make_image(600, 800),
        "resolución": make_image(400, 300),
        "no imagen": b"hola",
    }
    for index, (reason, data) in enumerate(bad_images.items()):
        response = _post(client, make_token(), image=data, key=f"i{index}")
        assert response.status_code == 400, reason
        assert response.json()["field"] == "image", reason
    assert location_repository.added == [] and image_store.saved == {}


def test_image_over_5_mb_is_rejected(client, make_token, location_repository) -> None:
    too_big = make_image(800, 600) + b"\0" * (5 * 1024 * 1024)
    response = _post(client, make_token(), image=too_big)
    assert response.status_code == 400
    assert "5 MB" in response.json()["message"]
    assert location_repository.added == []
