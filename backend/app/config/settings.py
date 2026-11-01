"""Configuración de la aplicación, leída desde variables de entorno."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de configuración. Ningún secreto va en el código."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    mysql_url: str
    mongo_url: str
    mongo_database: str = "pokearena"
    redis_url: str

    jwt_secret: str
    # Los algoritmos permitidos los define el servidor, no la cabecera del token.
    jwt_algorithms: list[str] = Field(default_factory=lambda: ["HS256"])
    jwt_issuer: str = "pokearena"
    jwt_audience: str = "pokearena-admin"
    jwt_expiration_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de la configuración."""
    return Settings()
