"""Errores del dominio. La capa de API los traduce a respuestas HTTP."""


class DomainError(Exception):
    """Base de los errores de negocio."""

    code = "domain_error"

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class NotAuthenticatedError(DomainError):
    """La solicitud no trae una sesión válida."""

    code = "not_authenticated"


class PermissionDeniedError(DomainError):
    """El usuario está autenticado pero no tiene permiso para la operación."""

    code = "permission_denied"


class ValidationFailedError(DomainError):
    """Un dato no cumple un requisito. Indica el campo afectado."""

    code = "validation_failed"


class ConflictError(DomainError):
    """La operación choca con el estado actual (por ejemplo, un recurso agotado)."""

    code = "conflict"
