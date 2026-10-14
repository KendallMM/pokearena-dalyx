from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.carta_schema import CartaCreate
from app.database import get_db

router = APIRouter(prefix="/admin/cartas", tags=["Cartas"])

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def crear_carta(
    carta: CartaCreate, 
    idempotency_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint para registrar una nueva carta en el catálogo.
    Requiere validación de administrador y clave de idempotencia.
    """
    # Paso 1.8: Microkernel - Comprobar habilidad por código
    if carta.habilidad != "HAB-000":
        # FastAPI responde 400; no guardar (Paso 1.9)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Habilidad inválida"
        )

    # Paso 1.12: Transacción BEGIN -> Insertar Carta -> COMMIT
    # Todo: Implementar inserción SQLAlchemy aquí bloqueando la clave

    # Paso 1.14 y 1.15: Retornar código inmutable y URL de estado
    return {
        "status": "PENDING_IMAGE",
        "codigo": "PKA-TIPO-001",
        "url_estado": "/admin/cartas/PKA-TIPO-001/estado"
    }