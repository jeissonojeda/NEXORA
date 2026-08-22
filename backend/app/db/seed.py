from sqlalchemy.orm import Session

from app.core.rbac import ALL_PERMISSIONS, ALL_ROLES, ROLE_PERMISSIONS
from app.models.role import Permission, Role
from app.repositories.rbac_repository import PermissionRepository, RoleRepository


def seed_rbac(db: Session) -> dict[str, int]:
    role_repo = RoleRepository(db)
    permission_repo = PermissionRepository(db)

    existing_roles = {role.name for role in role_repo.get_all()}
    created_roles = 0
    role_by_name: dict[str, Role] = {
        role.name: role for role in role_repo.get_all()
    }

    for role_data in ALL_ROLES:
        if role_data["name"] not in existing_roles:
            role = Role(
                name=role_data["name"],
                display_name=role_data["display_name"],
            )
            role_repo.add(role)
            role_by_name[role.name] = role
            created_roles += 1

    existing_codes = {
        code
        for code, in db.query(Permission.code).all()
    }
    created_permissions = 0
    for code, description in ALL_PERMISSIONS.items():
        if code not in existing_codes:
            permission_repo.add(Permission(code=code, description=description))
            created_permissions += 1

    db.flush()

    assigned_links = 0
    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        current_codes = {p.code for p in role.permissions}
        missing = permission_codes - current_codes
        if missing:
            permissions = permission_repo.get_by_codes(missing)
            role.permissions.extend(permissions)
            assigned_links += len(permissions)

    db.commit()
    return {
        "roles_created": created_roles,
        "permissions_created": created_permissions,
        "permission_links_added": assigned_links,
    }
