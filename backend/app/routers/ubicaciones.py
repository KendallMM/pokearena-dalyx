import uuid
import json
from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, redis_client, get_mongo

# Asumiendo que guardaste el modelo en app/models/ubicacion_model.py
from app.models.ubicacion_model import Ubicacion 

router = APIRouter(prefix="/admin/ubicaciones", tags=["Ubicaciones"])

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def crear_ubicacion(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    efecto: str = Form(...),
    cupo: int = Form(...),
    energia: str = Form(...),
    imagen: UploadFile = File(...),
    idempotency_key: str = Header(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    mongo: dict = Depends(get_mongo)
):
    # Paso 1.6: Verificar Idempotencia
    cached_response = await redis_client.get(idempotency_key)
    if cached_response:
        return json.loads(cached_response)

    # Paso 1.8: Validar cupo entero 0..5
    if not (0 <= cupo <= 5):
        raise HTTPException(status_code=400, detail="El cupo debe estar entre 0 y 5.")

    # Paso 1.10: Validar PNG/JPG/WebP y peso <= 5 MB
    if imagen.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Formato de imagen inválido.")
    
    file_bytes = await imagen.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen supera los 5 MB permitidos.")

    codigo_generado = f"PKA-UBI-{str(uuid.uuid4())[:4].upper()}"

    # Guardar original temporal en MongoDB
    await mongo["imagenes_ubicaciones"].insert_one({
        "codigo": codigo_generado,
        "filename": imagen.filename,
        "content_type": imagen.content_type,
        "data": file_bytes,
        "estado": "TEMPORAL"
    })

    # Paso 1.12: Transacción BD
    nueva_ubicacion = Ubicacion(
        codigo=codigo_generado,
        nombre=nombre,
        descripcion=descripcion,
        efecto=efecto,
        cupo=cupo,
        energia=energia,
        estado="PENDING_IMAGE"
    )
    
    try:
        db.add(nueva_ubicacion)
        await db.commit()
        await db.refresh(nueva_ubicacion)
    except Exception as e:
        await db.rollback()
        await mongo["imagenes_ubicaciones"].delete_one({"codigo": codigo_generado})
        raise HTTPException(status_code=500, detail="Error transaccional.")

    response_data = {
        "status": nueva_ubicacion.estado,
        "codigo": nueva_ubicacion.codigo,
        "url_estado": f"/admin/ubicaciones/{nueva_ubicacion.codigo}/estado"
    }
    
    await redis_client.set(idempotency_key, json.dumps(response_data), ex=86400)
    
    return response_data