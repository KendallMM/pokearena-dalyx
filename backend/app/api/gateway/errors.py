"""Contrato de error único: todas las respuestas de error tienen la misma forma."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.gateway.correlation import CORRELATION_HEADER
from app.business.shared.errors import (
    ConflictError,
    DomainError,
    NotAuthenticatedError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Forma de toda respuesta de error de la API."""

    code: str
    message: str
    field: str | None = None
    correlation_id: str | None = None


# Respuestas de error que documenta OpenAPI en los endpoints de administración.
AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Usuario no autenticado."},
    403: {"model": ErrorResponse, "description": "Usuario sin permiso."},
}
ADMIN_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Dato o requisito incumplido."},
    **AUTH_ERROR_RESPONSES,
}
CONFLICT_RESPONSE: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorResponse,
        "description": "La operación choca con el estado actual.",
    },
}

NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "El recurso no existe."},
}

# El negocio no conoce HTTP: la traducción vive aquí.
STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (ServiceUnavailableError, 503),
    (NotAuthenticatedError, 401),
    (PermissionDeniedError, 403),
    (ValidationFailedError, 400),
    (NotFoundError, 404),
    (ConflictError, 409),
]


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    correlation_id = _correlation_id(request)
    body = ErrorResponse(
        code=code, message=message, field=field, correlation_id=correlation_id
    )
    response_headers = dict(headers or {})
    if correlation_id:
        response_headers[CORRELATION_HEADER] = correlation_id
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=response_headers
    )


def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    for error_type, status_code in STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
            return _error_response(
                request, status_code, exc.code, exc.message, exc.field, headers
            )
    logger.error("Error de dominio sin respuesta HTTP definida: %s", exc.code)
    return _internal_error(request)


def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    first = exc.errors()[0]
    field = str(first["loc"][-1]) if first["loc"] else None
    return _error_response(
        request, 400, "validation_failed", f"Valor inválido: {first['msg']}", field
    )


def _internal_error(request: Request) -> JSONResponse:
    return _error_response(
        request, 500, "internal_error", "Ocurrió un error inesperado."
    )


def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Error no controlado", exc_info=exc)
    return _internal_error(request)


def register_error_handlers(app: FastAPI) -> None:
    """Registra la traducción de errores a respuestas HTTP."""
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
