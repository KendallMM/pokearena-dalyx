"""Configuración de la aplicación, leída desde variables de entorno."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de configuración. Ningún secreto va en el código."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    mysql_url: str
    mongo_url: str
    mongo_database: str = "pokearena"
    redis_url: str

    jwt_secret: str = Field(min_length=32)
    # Los algoritmos permitidos los define el servidor, no la cabecera del token.
    jwt_algorithms: list[str] = Field(default_factory=lambda: ["HS256"])
    jwt_issuer: str = "pokearena"
    jwt_audience: str = "pokearena-admin"
    jwt_expiration_minutes: int = Field(default=15, ge=1, le=60)

    google_client_id: str = ""
    google_timeout_seconds: float = Field(default=5, gt=0, le=30)
    login_challenge_seconds: int = Field(default=300, ge=60, le=600)
    public_app_url: str = "http://localhost:5173"
    initial_card_codes: list[str] = Field(default_factory=list)
    initial_cubes: int | None = Field(default=None, ge=0)
    initial_collection_retry_seconds: int = Field(default=60, ge=1)

    @field_validator("initial_cubes", mode="before")
    @classmethod
    def optional_initial_cubes(cls, value: object) -> object:
        """Permite dejar la recompensa sin configurar en Compose o .env."""
        return None if value in ("", "null") else value

    @field_validator("initial_card_codes")
    @classmethod
    def unique_initial_cards(cls, values: list[str]) -> list[str]:
        """Cada código representa una carta real y no puede repetirse."""
        if len(values) != len(set(values)) or any(
            not value.strip() for value in values
        ):
            raise ValueError(
                "Los códigos de cartas iniciales deben ser únicos y no vacíos."
            )
        return values

    # Tiempo que se conserva la respuesta de una operación ya registrada.
    idempotency_ttl_seconds: int = 86400
    log_level: str = "INFO"

    # Tarea automática de miniaturas (ADR-002). Los valores finales los fija el ADR
    # de tareas automáticas.
    scheduler_enabled: bool = True
    thumbnail_interval_seconds: float = 5
    thumbnail_batch_size: int = 20
    thumbnail_lease_seconds: int = (
        120  # cuánto tiempo "reserva" una instancia una carta
    )
    thumbnail_retry_delay_seconds: int = 60  # espera antes de reintentar una carta


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de la configuración."""
    return Settings()
