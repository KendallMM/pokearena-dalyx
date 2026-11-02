"""API de Administración: referencias para los formularios."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from app.api.caching import compute_etag, etag_matches
from app.api.gateway.authentication import require_content_admin
from app.api.gateway.errors import AUTH_ERROR_RESPONSES
from app.api.schemas.references import ReferencesResponse
from app.business.catalog.references.reference_service import ReferenceService
from app.business.identity_access.roles import Actor

router = APIRouter(prefix="/admin", tags=["Administración"])

CACHE_CONTROL = "private, no-cache"


def get_reference_service(request: Request) -> ReferenceService:
    """Obtiene el servicio armado al iniciar la aplicación."""
    return request.app.state.reference_service


@router.get(
    "/referencias",
    response_model=ReferencesResponse,
    summary="Cargar las referencias de los formularios",
    description=(
        "Devuelve en una sola llamada los tipos, las rarezas y las habilidades "
        "disponibles. Incluye ETag: con If-None-Match la API responde 304 si no hay cambios."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        304: {"description": "Las referencias no han cambiado."},
    },
)
def get_references(
    _actor: Actor = Depends(require_content_admin),
    service: ReferenceService = Depends(get_reference_service),
    if_none_match: str | None = Header(default=None),
) -> Response:
    """Lee las referencias y las entrega con su ETag."""
    references = service.get_references()
    payload = ReferencesResponse.model_validate(asdict(references)).model_dump()
    etag = compute_etag(payload)
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)
