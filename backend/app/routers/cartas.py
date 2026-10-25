import uuid
import json
import io
from PIL import Image
from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy.future import select
from app.database import async_session, get_db, redis_client, get_mongo
from app.models.carta_model import Carta
from app.engine.ability_engine import ability_engine
from app.schemas.carta_schema import PaginatedCartas

router = APIRouter(prefix="/admin/cartas", tags=["Cartas"])

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def crear_carta(
    nombre: str = Form(...),
    costo: int = Form(...),
    poder: int = Form(...),
    tipo: str = Form(...),
    rareza: str = Form(...),
    habilidad: str = Form(...),
    imagen: UploadFile = File(...),
    idempotency_key: str = Header(...),
    background_tasks: BackgroundTasks = None, # <-- Parámetro inyectado por FastAPI
    db: AsyncSession = Depends(get_db),
    mongo: dict = Depends(get_mongo)
):
    # Paso 1.6: Verificar Idempotencia
    cached_response = await redis_client.get(idempotency_key)
    if cached_response:
        return json.loads(cached_response)

    # Paso 1.8: Microkernel - Comprobar habilidad
    if not ability_engine.validar_habilidad(habilidad):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Habilidad '{habilidad}' no registrada."
        )

    # Paso 1.10: Validar PNG/JPG/WebP y peso <= 5 MB
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if imagen.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Formato de imagen inválido. Use JPG, PNG o WebP.")
    
    file_bytes = await imagen.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen supera los 5 MB permitidos.")

    codigo_generado = f"PKA-{tipo[:3].upper()}-{str(uuid.uuid4())[:4].upper()}"

    # Guardar original temporal en MongoDB
    imagen_doc = {
        "codigo": codigo_generado,
        "filename": imagen.filename,
        "content_type": imagen.content_type,
        "data": file_bytes,
        "estado": "TEMPORAL"
    }
    await mongo["imagenes_cartas"].insert_one(imagen_doc)

    # Paso 1.12: Guardado transaccional en PostgreSQL
    nueva_carta = Carta(
        codigo=codigo_generado, nombre=nombre, costo=costo, 
        poder=poder, tipo=tipo, rareza=rareza, 
        habilidad=habilidad, estado="PENDING_IMAGE"
    )
    
    try:
        db.add(nueva_carta)
        await db.commit()
        await db.refresh(nueva_carta)
    except Exception as e:
        await db.rollback()
        await mongo["imagenes_cartas"].delete_one({"codigo": codigo_generado}) # Limpieza temporal
        raise HTTPException(status_code=500, detail="Error transaccional al guardar carta")

    response_data = {
        "status": nueva_carta.estado,
        "codigo": nueva_carta.codigo,
        "url_estado": f"/admin/cartas/{nueva_carta.codigo}/estado"
    }
    await redis_client.set(idempotency_key, json.dumps(response_data), ex=86400)
    
    # Despachar trabajo diferido (Paso 2.1)
    if background_tasks:
        background_tasks.add_task(
            procesar_imagen, 
            codigo_generado, 
            file_bytes, 
            imagen.content_type, 
            mongo
        )
    
    return response_data

@router.get("/{codigo}/estado", status_code=status.HTTP_200_OK)
async def consultar_estado_carta(codigo: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.future import select
    result = await db.execute(select(Carta).where(Carta.codigo == codigo))
    carta = result.scalars().first()
    if not carta:
        raise HTTPException(status_code=404, detail="Carta no encontrada.")
    return {"codigo": carta.codigo, "nombre": carta.nombre, "estado": carta.estado, "tipo": carta.tipo}

async def procesar_imagen(codigo: str, image_bytes: bytes, formato: str, mongo_db):
    try:
        # Paso 2.2: Crear miniatura 200x280
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((200, 280))
        thumb_io = io.BytesIO()
        img.save(thumb_io, format=img.format if img.format else "JPEG")
        
        # Guardar estado READY y miniatura en MongoDB
        await mongo_db["imagenes_cartas"].update_one(
            {"codigo": codigo},
            {"$set": {"thumbnail": thumb_io.getvalue(), "estado": "READY"}}
        )

        # Paso 2.4: Marcar READY en PostgreSQL usando una sesión nueva
        async with async_session() as db:
            from sqlalchemy.future import select
            from app.models.carta_model import Carta
            result = await db.execute(select(Carta).where(Carta.codigo == codigo))
            carta = result.scalars().first()
            if carta:
                carta.estado = "READY"
                await db.commit()

    except Exception as e:
        # Paso 2.3: En caso de falla, marcar como RETRY_IMAGE
        async with async_session() as db:
            from sqlalchemy.future import select
            from app.models.carta_model import Carta
            result = await db.execute(select(Carta).where(Carta.codigo == codigo))
            carta = result.scalars().first()
            if carta:
                carta.estado = "RETRY_IMAGE"
                await db.commit()

@router.get("/", response_model=PaginatedCartas, status_code=status.HTTP_200_OK)
async def buscar_cartas(
    tipo: Optional[str] = None,
    costo: Optional[int] = None,
    rareza: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    last_id: int = Query(0, description="ID de la última carta recuperada"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Carta)
    
    # Aplicación de filtros de búsqueda
    if tipo:
        query = query.where(Carta.tipo == tipo)
    if costo is not None:
        query = query.where(Carta.costo == costo)
    if rareza:
        query = query.where(Carta.rareza == rareza)
        
    # Paginación estricta por cursor (diagrama de secuencia)
    if last_id > 0:
        query = query.where(Carta.id > last_id)
        
    # Ordenamiento por índice primario para consistencia del cursor
    query = query.order_by(Carta.id.asc()).limit(limit)
    
    result = await db.execute(query)
    cartas = result.scalars().all()
    
    nuevo_cursor = cartas[-1].id if cartas else None
    
    return {
        "resultados": cartas,
        "limit": limit,
        "next_cursor": nuevo_cursor,
        "count": len(cartas)
    }