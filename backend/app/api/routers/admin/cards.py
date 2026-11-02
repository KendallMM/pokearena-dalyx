"""API de Administración: cartas."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.gateway.errors import ADMIN_ERROR_RESPONSES, CONFLICT_RESPONSE
from app.api.gateway.idempotency import IdempotencyContext, idempotency_context
from app.api.schemas.cards import CardAcceptedResponse
from app.business.catalog.content.cards.card_service import CardService
from app.business.catalog.content.cards.models import CreateCard
from app.business.image_processing.models import MAX_IMAGE_BYTES
from app.business.shared.errors import ValidationFailedError

router = APIRouter(prefix="/admin", tags=["Administración"])


def get_card_service(request: Request) -> CardService:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.card_service


@router.post(
    "/cartas",
    status_code=202,
    response_model=CardAcceptedResponse,
    summary="Crear una carta",
    description=(
        "Crea la carta con su imagen (PNG, JPG o WebP, máximo 5 MB, proporción 5:7 y "
        "mínimo 600 × 840). La respuesta es 202: la versión pequeña se genera después "
        "y la carta queda disponible cuando existen las dos versiones. Requiere el "
        "encabezado Idempotency-Key: repetir la misma operación devuelve la respuesta "
        "guardada sin crear otra carta."
    ),
    responses={**ADMIN_ERROR_RESPONSES, **CONFLICT_RESPONSE},
)
def create_card(
    name: str = Form(description="Nombre de la carta"),
    cost: int = Form(description="Costo, de 0 a 10"),
    power: int = Form(description="Poder, de -20 a 20"),
    card_type: str = Form(description="Código del tipo, por ejemplo FUE"),
    rarity: str = Form(description="Código de la rareza, por ejemplo COMMON"),
    ability: str | None = Form(default=None, description="Código de la habilidad"),
    image: UploadFile | None = File(default=None, description="Imagen de la carta"),
    ctx: IdempotencyContext = Depends(idempotency_context),
    service: CardService = Depends(get_card_service),
) -> JSONResponse:
    """Crea la carta y responde 202 con el código asignado."""
    if image is None:
        raise ValidationFailedError(
            "Debe adjuntar la imagen de la carta.", field="image"
        )
    # Se lee un byte de más para que la lógica detecte el exceso de peso sin cargar todo.
    image_data = image.file.read(MAX_IMAGE_BYTES + 1)

    stored = service.create_card(
        CreateCard(
            name=name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            ability=ability,
            image_data=image_data,
        )
    )
    body = CardAcceptedResponse(
        code=stored.code, status=stored.status.value, message="Carta en proceso"
    )
    return ctx.respond(202, body)
