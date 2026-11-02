"""Qué puede hacer cada rol."""

from enum import Enum

from app.business.identity_access.roles import Actor, Role
from app.business.shared.errors import PermissionDeniedError


class Permission(str, Enum):
    """Operaciones que requieren permiso."""

    MANAGE_CATALOG = "manage_catalog"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PLAYER: frozenset(),
    Role.CONTENT_ADMIN: frozenset({Permission.MANAGE_CATALOG}),
    Role.PARTNER_ADMIN: frozenset(),
}


def ensure_permission(actor: Actor, permission: Permission) -> None:
    """Lanza PermissionDeniedError si el rol del actor no tiene el permiso."""
    if permission not in ROLE_PERMISSIONS[actor.role]:
        raise PermissionDeniedError("No tiene permiso para realizar esta operación.")
