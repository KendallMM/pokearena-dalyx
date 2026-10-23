from sqlalchemy import Column, String, Integer
from app.database import Base

class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    codigo = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=False)
    efecto = Column(String, nullable=False)
    cupo = Column(Integer, nullable=False)
    energia = Column(String, nullable=False)
    estado = Column(String, default="PENDING_IMAGE", nullable=False)