"""POST /admin/cartas con la lógica real y dobles en la persistencia."""

from tests.unit.image_helpers import make_image

FORM = {
    "name": "Charmander",
    "cost": "3",
    "power": "5",
    "card_type": "FUE",
    "rarity": "COMMON",
    "ability": "HAB-000",
}


def _post(client, token, form=None, image=..., key="op-1", **extra_headers):
    headers = {"Authorization": f"Bearer {token}", **extra_headers}
    if key is not None:
        headers["Idempotency-Key"] = key
    files = None
    if image is ...:
        image = make_image(600, 840)
    if image is not None:
        files = {"image": ("carta.png", image, "image/png")}
    return client.post(
        "/admin/cartas",
        data=form if form is not None else FORM,
        files=files,
        headers=headers,
    )


def test_without_credentials_returns_401(client) -> None:
    response = client.post("/admin/cartas", data=FORM)
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_without_admin_role_returns_403_and_saves_nothing(
    client, make_token, image_store
) -> None:
    response = _post(client, make_token(role="player"))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert image_store.saved == {}


def test_creates_card_and_returns_202_with_code(client, make_token) -> None:
    response = _post(client, make_token())
    assert response.status_code == 202
    assert response.json() == {
        "code": "PKA-FUE-001",
        "status": "pending_thumbnail",
        "message": "Carta en proceso",
    }


def test_repeating_the_operation_returns_stored_response_without_new_card(
    client, make_token, card_repository, image_store
) -> None:
    token = make_token()
    first = _post(client, token)
    second = _post(client, token)
    assert second.status_code == 202
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert len(card_repository.added) == 1  # no se crea otra carta ni se gasta código
    assert len(image_store.saved) == 1


def test_a_new_operation_gets_the_next_code(client, make_token) -> None:
    token = make_token()
    codes = [_post(client, token, key=k).json()["code"] for k in ["a", "b"]]
    assert codes == ["PKA-FUE-001", "PKA-FUE-002"]


def test_missing_operation_id_returns_400(client, make_token) -> None:
    response = _post(client, make_token(), key=None)
    assert response.status_code == 400
    assert response.json()["field"] == "Idempotency-Key"


def test_invalid_values_return_400_naming_the_field(
    client, make_token, image_store, card_repository
) -> None:
    cases = {
        "cost": {**FORM, "cost": "11"},
        "power": {**FORM, "power": "-21"},
        "card_type": {**FORM, "card_type": "XXX"},
        "rarity": {**FORM, "rarity": "MYTHIC"},
        "ability": {**FORM, "ability": "HAB-404"},
        "name": {**FORM, "name": " "},
    }
    for index, (field, form) in enumerate(cases.items()):
        response = _post(client, make_token(), form=form, key=f"k{index}")
        assert response.status_code == 400, field
        assert response.json()["field"] == field
    assert image_store.saved == {} and card_repository.added == []


def test_non_numeric_cost_returns_400_naming_the_field(client, make_token) -> None:
    response = _post(client, make_token(), form={**FORM, "cost": "abc"})
    assert response.status_code == 400
    assert response.json()["field"] == "cost"


def test_missing_ability_asks_to_choose_one(client, make_token) -> None:
    form = {k: v for k, v in FORM.items() if k != "ability"}
    response = _post(client, make_token(), form=form)
    assert response.status_code == 400
    assert response.json()["field"] == "ability"
    assert "Sin Habilidad" in response.json()["message"]


def test_missing_image_returns_400(client, make_token) -> None:
    response = _post(client, make_token(), image=None)
    assert response.status_code == 400
    assert response.json()["field"] == "image"


def test_invalid_images_return_400_and_card_is_not_saved(
    client, make_token, card_repository, image_store
) -> None:
    bad_images = {
        "formato": make_image(600, 840, "GIF"),
        "proporción": make_image(840, 600),
        "resolución": make_image(500, 700),
        "no imagen": b"hola",
    }
    for index, (reason, data) in enumerate(bad_images.items()):
        response = _post(client, make_token(), image=data, key=f"i{index}")
        assert response.status_code == 400, reason
        assert response.json()["field"] == "image", reason
    assert card_repository.added == [] and image_store.saved == {}


def test_image_over_5_mb_returns_400(client, make_token) -> None:
    response = _post(client, make_token(), image=b"x" * (5 * 1024 * 1024 + 10))
    assert response.status_code == 400
    assert "5 MB" in response.json()["message"]


def test_failed_request_can_be_retried_with_the_same_operation_id(
    client, make_token
) -> None:
    token = make_token()
    bad = _post(client, token, form={**FORM, "cost": "99"}, key="same")
    good = _post(client, token, key="same")
    assert bad.status_code == 400
    assert good.status_code == 202


def test_openapi_documents_the_endpoint(client) -> None:
    operation = client.app.openapi()["paths"]["/admin/cartas"]["post"]
    assert {"202", "400", "401", "403", "409"} <= set(operation["responses"])
