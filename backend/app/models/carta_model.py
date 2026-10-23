from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Carta(Base):
    __tablename__ = "cartas"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, index=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    costo = Column(Integer, index=True, nullable=False)
    poder = Column(Integer, nullable=False)
    tipo = Column(String(50), index=True, nullable=False)
    rareza = Column(String(50), index=True, nullable=False)
    habilidad = Column(String(50), nullable=False)
    estado = Column(String(50), nullable=False, default="PENDING_IMAGE")