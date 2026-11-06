"""API Gateway, mensaje 7: asigna la correlación antes de llegar a la API.

El mismo identificador acompaña los errores 503 y 401 de los mensajes 14 y 20,
para relacionar lo que ve el jugador con la solicitud atendida por el backend.
"""

import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.logging import correlation_id_var

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware:
    """Toma el identificador de la solicitud o crea uno, y lo devuelve en la respuesta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        incoming = headers.get(CORRELATION_HEADER.lower().encode(), b"").decode()
        correlation_id = incoming[:64] or uuid.uuid4().hex
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        token = correlation_id_var.set(correlation_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers_list = message.setdefault("headers", [])
                name = CORRELATION_HEADER.lower().encode()
                # Los errores ya lo traen; no se repite.
                if not any(key.lower() == name for key, _ in headers_list):
                    headers_list.append((name, correlation_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            correlation_id_var.reset(token)
