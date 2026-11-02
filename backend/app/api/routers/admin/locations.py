"""API de Administración: ubicaciones."""

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.gateway.errors import ADMIN_ERROR_RESPONSES, CONFLICT_RESPONSE
from app.api.gateway.idempotency import IdempotencyContext, idempotency_context
from app.api.schemas.locations import LocationAcceptedResponse
from app.business.catalog.content.locations.location_service import LocationService
from app.business.catalog.content.locations.models import CreateLocation
from app.business.image_processing.models import MAX_IMAGE_BYTES
from app.business.shared.errors import ValidationFailedError

router = APIRouter(prefix="/admin", tags=["Administración"])


def get_location_service(request: Request) -> LocationService:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.location_service


def _parse_effect_parameters(raw: str | None) -> dict[str, Any] | None:
    """Los parámetros llegan como texto JSON porque el formulario también lleva la
    imagen. Aquí solo se lee la estructura; las reglas viven en la lógica."""
    if raw is None or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        raise ValidationFailedError(
            "Los parámetros del efecto deben ser un objeto JSON.",
            field="effect_parameters",
        ) from None
    if not isinstance(parsed, dict):
        raise ValidationFailedError(
            "Los parámetros del efecto deben ser un objeto JSON.",
            field="effect_parameters",
        )
    return parsed


@router.post(
    "/ubicaciones",
    status_code=202,
    response_model=LocationAcceptedResponse,
    summary="Crear una ubicación",
    description=(
        "Crea la ubicación con su imagen (PNG, JPG o WebP, máximo 5 MB, proporción 4:3 "
        "y mínimo 800 × 600). El efecto es opcional: se elige un tipo del catálogo de "
        "GET /admin/referencias y sus parámetros se envían como objeto JSON en "
        "effect_parameters. La energía extra es fija (0 a 3 por jugador) o por cartas "
        "(0 a 2 por cada carta propia en la ubicación). La respuesta es 202: la versión "
        "pequeña se genera después y la ubicación puede asignarse a partidas cuando "
        "existen las dos versiones. Requiere el encabezado Idempotency-Key: repetir la "
        "misma operación devuelve la respuesta guardada sin crear otra ubicación."
    ),
    responses={**ADMIN_ERROR_RESPONSES, **CONFLICT_RESPONSE},
)
def create_location(
    name: str = Form(description="Nombre de la ubicación"),
    description: str = Form(description="Descripción de la ubicación"),
    card_limit: int = Form(description="Límite de cartas por jugador, de 0 a 5"),
    extra_energy_mode: str = Form(description="fixed o per_card"),
    extra_energy_amount: int = Form(
        description="Monto de energía extra: de 0 a 3 (fixed) o de 0 a 2 (per_card)"
    ),
    effect_type: str | None = Form(
        default=None, description="Código del tipo de efecto. Vacío: sin efecto"
    ),
    effect_parameters: str | None = Form(
        default=None,
        description='Parámetros del efecto en JSON, por ejemplo {"amount": 2}',
    ),
    image: UploadFile | None = File(default=None, description="Imagen de la ubicación"),
    ctx: IdempotencyContext = Depends(idempotency_context),
    service: LocationService = Depends(get_location_service),
) -> JSONResponse:
    """Crea la ubicación y responde 202 con su identificador."""
    if image is None:
        raise ValidationFailedError(
            "Debe adjuntar la imagen de la ubicación.", field="image"
        )
    parameters = _parse_effect_parameters(effect_parameters)
    # Se lee un byte de más para que la lógica detecte el exceso de peso sin cargar todo.
    image_data = image.file.read(MAX_IMAGE_BYTES + 1)

    stored = service.create_location(
        CreateLocation(
            name=name,
            description=description,
            card_limit=card_limit,
            extra_energy_mode=extra_energy_mode,
            extra_energy_amount=extra_energy_amount,
            effect_type=effect_type,
            effect_parameters=parameters,
            image_data=image_data,
        )
    )
    body = LocationAcceptedResponse(
        id=stored.id, status=stored.status.value, message="Ubicación en proceso"
    )
    return ctx.respond(202, body)
