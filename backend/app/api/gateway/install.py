"""Instala el API Gateway en la aplicación FastAPI."""

from fastapi import FastAPI

from app.api.gateway.correlation import CorrelationIdMiddleware
from app.api.gateway.errors import register_error_handlers
from app.api.gateway.idempotency import register_idempotency_handler


def install_gateway(app: FastAPI) -> None:
    """Agrega correlación, contrato de error e idempotencia."""
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    register_idempotency_handler(app)
