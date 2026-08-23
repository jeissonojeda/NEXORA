class Roles:
    ADMIN = "ADMIN"
    CASHIER = "CASHIER"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"


ALL_ROLES: list[dict[str, str]] = [
    {"name": Roles.ADMIN, "display_name": "Administrador"},
    {"name": Roles.CASHIER, "display_name": "Cajero"},
    {"name": Roles.INVENTORY_MANAGER, "display_name": "Encargado de inventario"},
]


class Permissions:
    USERS_READ = "users.read"
    USERS_CREATE = "users.create"
    USERS_UPDATE = "users.update"
    USERS_DELETE = "users.delete"

    PRODUCTS_READ = "products.read"
    PRODUCTS_CREATE = "products.create"
    PRODUCTS_UPDATE = "products.update"
    PRODUCTS_DELETE = "products.delete"

    CATEGORIES_READ = "categories.read"
    CATEGORIES_CREATE = "categories.create"
    CATEGORIES_UPDATE = "categories.update"
    CATEGORIES_DELETE = "categories.delete"

    INVENTORY_READ = "inventory.read"
    INVENTORY_CREATE = "inventory.create"
    INVENTORY_UPDATE = "inventory.update"

    SALES_READ = "sales.read"
    SALES_CREATE = "sales.create"

    CUSTOMERS_READ = "customers.read"
    CUSTOMERS_CREATE = "customers.create"
    CUSTOMERS_UPDATE = "customers.update"

    SUPPLIERS_READ = "suppliers.read"
    SUPPLIERS_CREATE = "suppliers.create"
    SUPPLIERS_UPDATE = "suppliers.update"
    SUPPLIERS_DELETE = "suppliers.delete"

    PURCHASES_READ = "purchases.read"
    PURCHASES_CREATE = "purchases.create"
    PURCHASES_UPDATE = "purchases.update"
    PURCHASES_CONFIRM = "purchases.confirm"
    PURCHASES_CANCEL = "purchases.cancel"

    CASH_READ = "cash.read"
    CASH_OPEN = "cash.open"
    CASH_CLOSE = "cash.close"
    CASH_MOVEMENTS = "cash.movements"

    REPORTS_READ = "reports.read"
    REPORTS_EXPORT = "reports.export"

    AI_READ = "ai.read"
    AI_ANALYZE = "ai.analyze"


ALL_PERMISSIONS: dict[str, str] = {
    Permissions.USERS_READ: "Ver usuarios",
    Permissions.USERS_CREATE: "Crear usuarios",
    Permissions.USERS_UPDATE: "Actualizar usuarios",
    Permissions.USERS_DELETE: "Eliminar usuarios",
    Permissions.PRODUCTS_READ: "Ver productos",
    Permissions.PRODUCTS_CREATE: "Crear productos",
    Permissions.PRODUCTS_UPDATE: "Actualizar productos",
    Permissions.PRODUCTS_DELETE: "Eliminar productos",
    Permissions.CATEGORIES_READ: "Ver categorías",
    Permissions.CATEGORIES_CREATE: "Crear categorías",
    Permissions.CATEGORIES_UPDATE: "Actualizar categorías",
    Permissions.CATEGORIES_DELETE: "Eliminar categorías",
    Permissions.INVENTORY_READ: "Ver inventario",
    Permissions.INVENTORY_CREATE: "Registrar movimientos de inventario",
    Permissions.INVENTORY_UPDATE: "Ajustar inventario",
    Permissions.SALES_READ: "Consultar ventas",
    Permissions.SALES_CREATE: "Registrar ventas",
    Permissions.CUSTOMERS_READ: "Consultar clientes",
    Permissions.CUSTOMERS_CREATE: "Crear clientes",
    Permissions.CUSTOMERS_UPDATE: "Actualizar clientes",
    Permissions.SUPPLIERS_READ: "Consultar proveedores",
    Permissions.SUPPLIERS_CREATE: "Crear proveedores",
    Permissions.SUPPLIERS_UPDATE: "Actualizar proveedores",
    Permissions.SUPPLIERS_DELETE: "Eliminar proveedores",
    Permissions.PURCHASES_READ: "Consultar compras",
    Permissions.PURCHASES_CREATE: "Crear compras",
    Permissions.PURCHASES_UPDATE: "Editar compras",
    Permissions.PURCHASES_CONFIRM: "Confirmar compras",
    Permissions.PURCHASES_CANCEL: "Cancelar compras",
    Permissions.CASH_READ: "Consultar caja",
    Permissions.CASH_OPEN: "Abrir caja",
    Permissions.CASH_CLOSE: "Cerrar caja",
    Permissions.CASH_MOVEMENTS: "Registrar movimientos de caja",
    Permissions.REPORTS_READ: "Consultar reportes",
    Permissions.REPORTS_EXPORT: "Exportar reportes",
    Permissions.AI_READ: "Consultar análisis de IA",
    Permissions.AI_ANALYZE: "Ejecutar análisis de IA",
}


def _codes(*permissions: str) -> set[str]:
    return set(permissions)


ROLE_PERMISSIONS: dict[str, set[str]] = {
    Roles.ADMIN: _codes(*ALL_PERMISSIONS.keys()),
    Roles.CASHIER: _codes(
        Permissions.SALES_READ,
        Permissions.SALES_CREATE,
        Permissions.CUSTOMERS_READ,
        Permissions.CUSTOMERS_CREATE,
        Permissions.CUSTOMERS_UPDATE,
        Permissions.CASH_READ,
        Permissions.CASH_OPEN,
        Permissions.CASH_CLOSE,
        Permissions.CASH_MOVEMENTS,
        Permissions.PRODUCTS_READ,
        Permissions.CATEGORIES_READ,
        Permissions.INVENTORY_READ,
        Permissions.SUPPLIERS_READ,
        Permissions.PURCHASES_READ,
    ),
    Roles.INVENTORY_MANAGER: _codes(
        Permissions.PRODUCTS_READ,
        Permissions.PRODUCTS_CREATE,
        Permissions.PRODUCTS_UPDATE,
        Permissions.PRODUCTS_DELETE,
        Permissions.CATEGORIES_READ,
        Permissions.CATEGORIES_CREATE,
        Permissions.CATEGORIES_UPDATE,
        Permissions.CATEGORIES_DELETE,
        Permissions.INVENTORY_READ,
        Permissions.INVENTORY_CREATE,
        Permissions.INVENTORY_UPDATE,
        Permissions.SUPPLIERS_READ,
        Permissions.SUPPLIERS_CREATE,
        Permissions.SUPPLIERS_UPDATE,
        Permissions.SUPPLIERS_DELETE,
        Permissions.PURCHASES_READ,
        Permissions.PURCHASES_CREATE,
        Permissions.PURCHASES_UPDATE,
        Permissions.PURCHASES_CONFIRM,
        Permissions.PURCHASES_CANCEL,
        Permissions.REPORTS_READ,
        Permissions.REPORTS_EXPORT,
    ),
}
