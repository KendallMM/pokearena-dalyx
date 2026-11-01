"""API Gateway: autenticación, rol, idempotencia, contrato de error y correlación."""

from tests.conftest import SECRET  # noqa: F401

BODY = {"name": "Charmander", "cost": 3}


def _headers(token: str, key: str | None = "op-1") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_health_is_public(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_no_credentials_returns_401(client, handler_calls) -> None:
    response = client.post("/test/things", json=BODY, headers={"Idempotency-Key": "a"})
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert handler_calls == []


def test_invalid_token_returns_401(client) -> None:
    response = client.post("/test/things", json=BODY, headers=_headers("basura"))
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_authenticated_without_admin_role_returns_403(client, make_token) -> None:
    response = client.post(
        "/test/things", json=BODY, headers=_headers(make_token(role="player"))
    )
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_401_and_403_are_distinct_errors(client, make_token) -> None:
    no_session = client.post("/test/things", json=BODY)
    no_role = client.post(
        "/test/things", json=BODY, headers=_headers(make_token(role="player"))
    )
    assert no_session.json()["code"] != no_role.json()["code"]


def test_session_and_role_are_checked_before_the_idempotency_key(
    client, store, make_token
) -> None:
    """Sin sesión no se puede conocer si una operación ya existe."""
    store.data["user-1:POST:/test/things:op-1"] = object()  # type: ignore[assignment]
    response = client.post(
        "/test/things", json=BODY, headers={"Idempotency-Key": "op-1"}
    )
    assert response.status_code == 401


def test_new_request_is_processed_and_response_stored(
    client, store, make_token, handler_calls
) -> None:
    response = client.post("/test/things", json=BODY, headers=_headers(make_token()))
    assert response.status_code == 202
    assert response.json() == {"id": 1, "name": "Charmander"}
    assert handler_calls == ["Charmander"]
    assert len(store.data) == 1
    assert store.saved_ttls == [86400]


def test_repeated_request_returns_stored_response_without_reprocessing(
    client, make_token, handler_calls
) -> None:
    headers = _headers(make_token())
    first = client.post("/test/things", json=BODY, headers=headers)
    second = client.post("/test/things", json=BODY, headers=headers)
    assert second.status_code == 202
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert handler_calls == ["Charmander"]  # el endpoint corrió una sola vez


def test_same_key_from_another_user_is_not_a_replay(
    client, make_token, handler_calls
) -> None:
    client.post("/test/things", json=BODY, headers=_headers(make_token(sub="a")))
    other = client.post(
        "/test/things", json=BODY, headers=_headers(make_token(sub="b"))
    )
    assert "Idempotent-Replayed" not in other.headers
    assert len(handler_calls) == 2


def test_missing_idempotency_key_returns_400(client, make_token) -> None:
    response = client.post(
        "/test/things", json=BODY, headers=_headers(make_token(), key=None)
    )
    assert response.status_code == 400
    assert response.json()["field"] == "Idempotency-Key"


def test_invalid_field_returns_400_with_field_name(client, make_token) -> None:
    response = client.post(
        "/test/things", json={"name": "X", "cost": 11}, headers=_headers(make_token())
    )
    assert response.status_code == 400
    assert response.json()["code"] == "validation_failed"
    assert response.json()["field"] == "cost"


def test_failed_request_is_not_stored(client, store, make_token) -> None:
    client.post(
        "/test/things", json={"name": "X", "cost": 99}, headers=_headers(make_token())
    )
    assert store.data == {}


def test_unexpected_error_uses_contract_and_hides_details(client) -> None:
    response = client.get("/test/boom")
    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "internal_error"
    assert "sensibles" not in response.text


def test_correlation_id_is_echoed_and_in_error_body(client) -> None:
    response = client.post(
        "/test/things", json=BODY, headers={"X-Correlation-ID": "abc-123"}
    )
    assert response.headers["X-Correlation-ID"] == "abc-123"
    assert response.json()["correlation_id"] == "abc-123"


def test_correlation_id_is_generated_when_missing(client) -> None:
    response = client.get("/health")
    assert len(response.headers["X-Correlation-ID"]) >= 16
