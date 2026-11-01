"""Punto de entrada de la API."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Crea la aplicación FastAPI."""
    app = FastAPI(title="PokeArena API", version="0.1.0")

    @app.get("/health", tags=["Operación"], summary="Estado del servicio")
    def health() -> dict[str, str]:
        """Indica que el servicio está en ejecución."""
        return {"status": "ok"}

    return app


app = create_app()
