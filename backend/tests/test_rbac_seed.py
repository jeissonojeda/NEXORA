from sqlalchemy.orm import Session

from app.core.rbac import (
    ALL_PERMISSIONS,
    ALL_ROLES,
    ROLE_PERMISSIONS,
    Roles,
)
from app.db.seed import seed_rbac
from app.repositories.rbac_repository import RoleRepository


def test_seed_creates_all_roles_and_permissions(db_session: Session) -> None:
    result = seed_rbac(db_session)
    assert result["roles_created"] == len(ALL_ROLES)
    assert result["permissions_created"] == len(ALL_PERMISSIONS)

    roles = {r.name: r for r in RoleRepository(db_session).get_all()}
    assert set(roles) == {Roles.ADMIN, Roles.CASHIER, Roles.INVENTORY_MANAGER}
    assert roles[Roles.CASHIER].display_name == "Cajero"


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed_rbac(db_session)
    second = seed_rbac(db_session)
    assert first["roles_created"] == 3
    assert second["roles_created"] == 0
    assert second["permissions_created"] == 0
    assert second["permission_links_added"] == 0


def test_role_permission_assignments_match_catalog(db_session: Session) -> None:
    seed_rbac(db_session)
    roles = {r.name: r for r in RoleRepository(db_session).get_all()}

    cashier_codes = {p.code for p in roles[Roles.CASHIER].permissions}
    assert cashier_codes == ROLE_PERMISSIONS[Roles.CASHIER]
    assert "users.delete" not in cashier_codes

    inv_codes = {p.code for p in roles[Roles.INVENTORY_MANAGER].permissions}
    assert inv_codes == ROLE_PERMISSIONS[Roles.INVENTORY_MANAGER]

    admin_codes = {p.code for p in roles[Roles.ADMIN].permissions}
    assert admin_codes == set(ALL_PERMISSIONS)
