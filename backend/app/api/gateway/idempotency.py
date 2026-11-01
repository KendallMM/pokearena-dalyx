"""Idempotencia: una operación repetida devuelve la respuesta guardada."""

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.gateway.authentication import require_content_admin
from app.business.identity_access.roles import Actor
from app.business.shared.errors import ValidationFailedError
from app.business.shared.ports import IdempotencyStore, StoredResponse

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotent-Replayed"
MAX_KEY_LENGTH = 128


class IdempotentReplay(Exception):
    """La operación ya fue registrada: se devuelve su respuesta guardada."""

    def __init__(self, stored: StoredResponse) -> None:
        super().__init__("Operación ya registrada")
        self.stored = stored


@dataclass
class IdempotencyContext:
    """Permite al endpoint responder y guardar la respuesta de la operación."""

    store: IdempotencyStore
    key: str
    ttl_seconds: int

    def respond(self, status_code: int, body: Any) -> JSONResponse:
        """Guarda la respuesta junto al identificador y la devuelve."""
        payload = jsonable_encoder(body)
        self.store.save(
            self.key, StoredResponse(status_code, payload), self.ttl_seconds
        )
        return JSONResponse(status_code=status_code, content=payload)


def get_idempotency_store(request: Request) -> IdempotencyStore:
    """Obtiene la caché compartida armada al iniciar la aplicación."""
    return request.app.state.idempotency_store


def idempotency_context(
    request: Request,
    actor: Actor = Depends(require_content_admin),
    store: IdempotencyStore = Depends(get_idempotency_store),
    operation_id: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> IdempotencyContext:
    """Busca el identificador de operación. Va después de verificar sesión y rol."""
    if not operation_id or len(operation_id) > MAX_KEY_LENGTH:
        raise ValidationFailedError(
            "Falta el identificador de operación o es demasiado largo.",
            field=IDEMPOTENCY_HEADER,
        )
    # La clave incluye usuario, método y ruta: dos usuarios no se pisan.
    key = f"{actor.user_id}:{request.method}:{request.url.path}:{operation_id}"
    stored = store.get(key)
    if stored is not None:
        raise IdempotentReplay(stored)
    return IdempotencyContext(
        store=store,
        key=key,
        ttl_seconds=request.app.state.settings.idempotency_ttl_seconds,
    )


def _replay_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IdempotentReplay)
    return JSONResponse(
        status_code=exc.stored.status_code,
        content=exc.stored.body,
        headers={REPLAY_HEADER: "true"},
    )


def register_idempotency_handler(app: FastAPI) -> None:
    """Registra la respuesta para solicitudes repetidas."""
    app.add_exception_handler(IdempotentReplay, _replay_handler)
