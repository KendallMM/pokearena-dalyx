"""Autorización, límite e idempotencia para el ingreso a la fila."""

import logging
from dataclasses import dataclass
from hashlib import sha256

from fastapi import Depends, Request, Response
from fastapi.encoders import jsonable_encoder

from app.api.gateway.authentication import require_player
from app.api.gateway.idempotency import (
    IDEMPOTENCY_HEADER,
    MAX_KEY_LENGTH,
    get_idempotency_store,
)
from app.business.identity_access.roles import Actor
from app.business.shared.errors import (
    ConflictError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.business.shared.ports import IdempotencyStore, StoredResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchAccess:
    actor: Actor
    key_hash: str
    store: IdempotencyStore
    ttl: int

    @property
    def cache_key(self) -> str:
        return f"{self.actor.user_id}:POST:/v1/busquedas:{self.key_hash}"

    def previous_search(self, deck_id: str | None) -> str | None:
        """Obtiene el identificador de la búsqueda registrada para esta clave."""
        previous = self.store.get(self.cache_key)
        if previous is None:
            return None
        if previous.body["deck_id"] != deck_id:
            raise ConflictError(
                "La clave de operación ya pertenece a otra solicitud.",
                IDEMPOTENCY_HEADER,
            )
        logger.info(
            "Reintento de búsqueda %s desde caché compartida", previous.body["id"]
        )
        return previous.body["id"]

    def respond(self, response: Response, result, *, created: bool) -> None:
        """Guarda el resultado en Redis después de confirmar la operación en MySQL."""
        response.status_code = 202 if created else 200
        response.headers["Cache-Control"] = "no-store"
        try:
            self.store.save(
                self.cache_key,
                StoredResponse(response.status_code, jsonable_encoder(result)),
                self.ttl,
            )
        except ServiceUnavailableError:
            logger.warning(
                "La operación de búsqueda quedó registrada únicamente en MySQL"
            )
            raise


def require_search_access(
    request: Request,
    actor: Actor = Depends(require_player),
    store: IdempotencyStore = Depends(get_idempotency_store),
) -> SearchAccess:
    """Comprueba el límite de solicitudes y prepara la clave de idempotencia."""
    limiter = request.app.state.search_limiter
    try:
        allowed = limiter is None or limiter.allow(f"match_search:{actor.user_id}")
    except ServiceUnavailableError:
        # ADR-004. Un fallo del limitador permite continuar. La idempotencia
        # sigue siendo obligatoria y devuelve 503 si su acceso a Redis falla.
        logger.warning(
            "Limitador de búsqueda indisponible; se continúa con la solicitud"
        )
        allowed = True
    if not allowed:
        raise RateLimitError(
            "Has realizado demasiadas solicitudes de búsqueda. Reintenta en unos segundos."
        )
    operation_id = request.headers.get(IDEMPOTENCY_HEADER)
    if (
        not operation_id
        or not operation_id.strip()
        or len(operation_id) > MAX_KEY_LENGTH
    ):
        raise ValidationFailedError(
            "Reintenta la operación con un identificador válido.", IDEMPOTENCY_HEADER
        )
    return SearchAccess(
        actor,
        sha256(operation_id.encode()).hexdigest(),
        store,
        request.app.state.settings.idempotency_ttl_seconds,
    )
