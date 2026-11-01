"""Punto de entrada de la API."""

from fastapi import FastAPI

from app.api.gateway.install import install_gateway
from app.api.routers.admin import references
from app.composition import Container, build_container
from app.config.settings import get_settings
from app.observability.logging import configure_logging


def create_app(container: Container | None = None) -> FastAPI:
    """Crea la aplicación. En pruebas se puede pasar un contenedor propio."""
    container = container or build_container(get_settings())
    configure_logging(container.settings.log_level)

    app = FastAPI(title="PokeArena API", version="0.1.0")
    app.state.settings = container.settings
    app.state.token_validator = container.token_validator
    app.state.idempotency_store = container.idempotency_store
    app.state.reference_service = container.reference_service
    install_gateway(app)
    app.include_router(references.router)

    @app.get("/health", tags=["Operación"], summary="Estado del servicio")
    def health() -> dict[str, str]:
        """Indica que el servicio está en ejecución."""
        return {"status": "ok"}

    return app
