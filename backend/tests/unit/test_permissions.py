"""Permisos por rol."""

import pytest

from app.business.identity_access.permissions import Permission, ensure_permission
from app.business.identity_access.roles import Actor, Role
from app.business.shared.errors import PermissionDeniedError


def test_content_admin_can_manage_catalog() -> None:
    ensure_permission(Actor("u", Role.CONTENT_ADMIN), Permission.MANAGE_CATALOG)


@pytest.mark.parametrize("role", [Role.PLAYER, Role.PARTNER_ADMIN])
def test_other_roles_cannot_manage_catalog(role: Role) -> None:
    with pytest.raises(PermissionDeniedError):
        ensure_permission(Actor("u", role), Permission.MANAGE_CATALOG)
