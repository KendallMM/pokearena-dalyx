"""Punto de entrada de la API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.gateway.install import install_gateway
from app.api.routers.admin import cards, references
from app.composition import Container, build_container
from app.config.settings import get_settings
from app.observability.logging import configure_logging


def create_app(container: Container | None = None) -> FastAPI:
    """Crea la aplicación. En pruebas se puede pasar un contenedor propio."""
    container = container or build_container(get_settings())
    configure_logging(container.settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # El planificador corre en su propio hilo, aparte de las solicitudes.
        if container.scheduler is not None:
            container.scheduler.start()
        try:
            yield
        finally:
            if container.scheduler is not None:
                container.scheduler.stop()

    app = FastAPI(title="PokeArena API", version="0.1.0", lifespan=lifespan)
    app.state.settings = container.settings
    app.state.token_validator = container.token_validator
    app.state.idempotency_store = container.idempotency_store
    app.state.reference_service = container.reference_service
    app.state.card_service = container.card_service
    install_gateway(app)
    app.include_router(references.router)
    app.include_router(cards.router)

    @app.get("/health", tags=["Operación"], summary="Estado del servicio")
    def health() -> dict[str, str]:
        """Indica que el servicio está en ejecución."""
        return {"status": "ok"}

    return app
