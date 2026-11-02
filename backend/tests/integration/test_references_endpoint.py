"""GET /admin/referencias: acceso, forma de la respuesta y ETag."""

from app.business.catalog.references.models import Rarity


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_without_credentials_returns_401(client) -> None:
    response = client.get("/admin/referencias")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_without_admin_role_returns_403(client, make_token) -> None:
    response = client.get(
        "/admin/referencias", headers=_auth(make_token(role="player"))
    )
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_returns_grouped_references(client, make_token) -> None:
    response = client.get("/admin/referencias", headers=_auth(make_token()))
    assert response.status_code == 200
    assert response.json() == {
        "card_types": [
            {"code": "FUE", "name": "Fuego"},
            {"code": "AGU", "name": "Agua"},
        ],
        "rarities": [
            {"code": "COMMON", "name": "Común"},
            {"code": "RARE", "name": "Rara"},
        ],
        "abilities": [
            {"code": "HAB-000", "name": "Sin Habilidad", "affected_card_type": None}
        ],
    }


def test_response_has_etag_and_revalidation_header(client, make_token) -> None:
    response = client.get("/admin/referencias", headers=_auth(make_token()))
    assert response.headers["ETag"].startswith('"')
    assert response.headers["Cache-Control"] == "private, no-cache"


def test_same_etag_returns_304_without_body(client, make_token) -> None:
    headers = _auth(make_token())
    etag = client.get("/admin/referencias", headers=headers).headers["ETag"]
    response = client.get(
        "/admin/referencias", headers={**headers, "If-None-Match": etag}
    )
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["ETag"] == etag


def test_etag_changes_when_references_change(
    client, make_token, reference_repository
) -> None:
    headers = _auth(make_token())
    old_etag = client.get("/admin/referencias", headers=headers).headers["ETag"]
    reference_repository.rarities.append(Rarity("LEGENDARY", "Legendaria"))
    response = client.get(
        "/admin/referencias", headers={**headers, "If-None-Match": old_etag}
    )
    assert response.status_code == 200
    assert response.headers["ETag"] != old_etag


def test_openapi_documents_the_endpoint(client) -> None:
    operation = client.app.openapi()["paths"]["/admin/referencias"]["get"]
    assert {"200", "304", "401", "403"} <= set(operation["responses"])
