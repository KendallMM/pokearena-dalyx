from pydantic import BaseModel, Field
from typing import List, Optional

class CartaCreate(BaseModel):
    """Modelo para validar la creación de una carta."""
    nombre: str = Field(..., min_length=1, max_length=100)
    imagen: str 
    costo: int = Field(..., ge=0, le=10, description="Energía entre 0 y 10")
    poder: int = Field(..., ge=-20, le=20, description="Poder entre -20 y 20")
    tipo: str = Field(..., min_length=1, description="Clasificación elemental")
    rareza: str = Field(..., min_length=1, description="Nivel de escasez")
    habilidad: str = Field(..., description="Código de habilidad (ej. HAB-000)")

class CartaOut(BaseModel):
    codigo: str
    nombre: str
    costo: int
    poder: int
    tipo: str
    rareza: str
    habilidad: str
    estado: str

    class Config:
        from_attributes = True

class PaginatedCartas(BaseModel):
    resultados: List[CartaOut]
    limit: int
    next_cursor: Optional[int]
    count: int