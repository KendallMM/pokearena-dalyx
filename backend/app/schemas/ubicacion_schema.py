from pydantic import BaseModel, Field

class UbicacionBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=255)
    efecto: str = Field(...)
    cupo: int = Field(..., ge=0, le=5)
    energia: str = Field(...)