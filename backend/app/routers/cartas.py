import uuid
import json
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.carta_schema import CartaCreate
from app.database import get_db, redis_client
from app.models.carta_model import Carta
from app.engine.ability_engine import ability_engine  # <-- Importamos el Microkernel

router = APIRouter(prefix="/admin/cartas", tags=["Cartas"])

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def crear_carta(
    carta: CartaCreate, 
    idempotency_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    # Paso 1.6: Verificar Idempotencia en Redis
    cached_response = await redis_client.get(idempotency_key)
    if cached_response:
        return json.loads(cached_response)

    # Paso 1.8: Microkernel - Comprobar habilidad por código dinámicamente
    if not ability_engine.validar_habilidad(carta.habilidad):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"El código de habilidad '{carta.habilidad}' no está registrado en el Microkernel."
        )

    # Generación de código inmutable
    codigo_generado = f"PKA-{carta.tipo[:3].upper()}-{str(uuid.uuid4())[:4].upper()}"

    # Paso 1.12: Transacción y guardado en PostgreSQL
    nueva_carta = Carta(
        codigo=codigo_generado,
        nombre=carta.nombre,
        costo=carta.costo,
        poder=carta.poder,
        tipo=carta.tipo,
        rareza=carta.rareza,
        habilidad=carta.habilidad,
        estado="PENDING_IMAGE"
    )
    
    try:
        db.add(nueva_carta)
        await db.commit()
        await db.refresh(nueva_carta)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error de base de datos al guardar la carta"
        )

    # Respuesta final
    response_data = {
        "status": nueva_carta.estado,
        "codigo": nueva_carta.codigo,
        "url_estado": f"/admin/cartas/{nueva_carta.codigo}/estado"
    }

    # Guardar en caché de Redis por 24 horas
    await redis_client.set(idempotency_key, json.dumps(response_data), ex=86400)

    return response_data