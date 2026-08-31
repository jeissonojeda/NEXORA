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
    SALES_UPDATE = "sales.update"
    SALES_CONFIRM = "sales.confirm"
    SALES_CANCEL = "sales.cancel"

    CUSTOMERS_READ = "customers.read"
    CUSTOMERS_CREATE = "customers.create"
    CUSTOMERS_UPDATE = "customers.update"
    CUSTOMERS_DELETE = "customers.delete"

    RECEIVABLES_READ = "receivables.read"
    RECEIVABLES_CREATE = "receivables.create"
    RECEIVABLES_PAYMENT = "receivables.payment"
    RECEIVABLES_CANCEL = "receivables.cancel"

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
    CASH_REPORT = "cash.report"

    REPORTS_READ = "reports.read"
    REPORTS_EXPORT = "reports.export"

    AI_READ = "ai.read"
    AI_ANALYZE = "ai.analyze"
    AI_EXECUTE = "ai.execute"
    AI_INVOICE = "ai.invoice"
    AI_INVENTORY = "ai.inventory"
    AI_PURCHASE = "ai.purchase"


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
    Permissions.SALES_UPDATE: "Editar ventas",
    Permissions.SALES_CONFIRM: "Confirmar ventas (cobrar)",
    Permissions.SALES_CANCEL: "Cancelar ventas",
    Permissions.CUSTOMERS_READ: "Consultar clientes",
    Permissions.CUSTOMERS_CREATE: "Crear clientes",
    Permissions.CUSTOMERS_UPDATE: "Actualizar clientes",
    Permissions.CUSTOMERS_DELETE: "Desactivar clientes",
    Permissions.RECEIVABLES_READ: "Consultar cuentas por cobrar",
    Permissions.RECEIVABLES_CREATE: "Crear cuentas por cobrar",
    Permissions.RECEIVABLES_PAYMENT: "Registrar pagos de cuentas por cobrar",
    Permissions.RECEIVABLES_CANCEL: "Anular cuentas por cobrar",
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
    Permissions.CASH_REPORT: "Consultar reportes de caja",
    Permissions.REPORTS_READ: "Consultar reportes",
    Permissions.REPORTS_EXPORT: "Exportar reportes",
    Permissions.AI_READ: "Consultar análisis de IA",
    Permissions.AI_ANALYZE: "Ejecutar análisis de IA",
    Permissions.AI_EXECUTE: "Confirmar acciones propuestas por IA",
    Permissions.AI_INVOICE: "Escaneo de facturas con IA",
    Permissions.AI_INVENTORY: "Ajustes de inventario vía IA",
    Permissions.AI_PURCHASE: "Compras propuestas por IA",
}


def _codes(*permissions: str) -> set[str]:
    return set(permissions)


ROLE_PERMISSIONS: dict[str, set[str]] = {
    Roles.ADMIN: _codes(*ALL_PERMISSIONS.keys()),
    Roles.CASHIER: _codes(
        Permissions.SALES_READ,
        Permissions.SALES_CREATE,
        Permissions.SALES_UPDATE,
        Permissions.SALES_CONFIRM,
        Permissions.SALES_CANCEL,
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
        Permissions.CUSTOMERS_READ,
        Permissions.CUSTOMERS_CREATE,
        Permissions.CUSTOMERS_UPDATE,
        Permissions.RECEIVABLES_READ,
        Permissions.RECEIVABLES_PAYMENT,
        # IA: solo lectura/consulta. El cajero NO puede confirmar acciones de
        # IA (ni compras, inventario o pagos vía IA) para evitar escalamiento.
        Permissions.AI_READ,
        Permissions.AI_ANALYZE,
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
        Permissions.SALES_READ,
        Permissions.CUSTOMERS_READ,
        Permissions.CUSTOMERS_CREATE,
        Permissions.CUSTOMERS_UPDATE,
        Permissions.REPORTS_READ,
        Permissions.REPORTS_EXPORT,
        # Sin permisos de caja: el rol de inventario no maneja efectivo.
        # IA operativa: el encargado de inventario puede escanear facturas,
        # proponer/adjustar inventario y compras, y confirmar acciones de IA.
        Permissions.AI_READ,
        Permissions.AI_ANALYZE,
        Permissions.AI_INVOICE,
        Permissions.AI_INVENTORY,
        Permissions.AI_PURCHASE,
        Permissions.AI_EXECUTE,
    ),
}
