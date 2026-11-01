"""Conexión a MySQL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_session_factory(url: str) -> sessionmaker[Session]:
    """Crea la fábrica de sesiones. No se conecta hasta la primera consulta."""
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)
