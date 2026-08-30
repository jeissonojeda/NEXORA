# Sistema de Facturación e Inventario con IA

Sistema web profesional para la gestión integral de un supermercado, con módulo de inteligencia artificial para análisis de ventas y recomendaciones de inventario.

## Estado

**Fase 1 — Fundamentos**, **Fase 2 — Autenticación, Usuarios y Roles**, **Fase 3 — Productos e Inventario**, **Fase 4 — Proveedores**, **Fase 5 — Compras y Abastecimiento**, **Fase 6 — Clientes y Cuentas por Cobrar**, **Fase 7 — Ventas y Facturación**, **Fase 8 — Caja y Control de Efectivo**, **Fase 9 — Reportes y Exportación**, **Fase 10 — Inteligencia Artificial** y **Fase 11 — Rediseño UX/UI Profesional (NEXORA)** completadas.

## Arquitectura

Monolito modular: backend API REST + frontend SPA, desplegables de forma independiente.

```
[Frontend React] ←→ [FastAPI Backend] ←→ [PostgreSQL]
                         ↓
                   [OpenAI API]
```

Documentación completa: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Tecnologías

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 15+, JWT (python-jose), bcrypt

**Frontend:** React 19, Vite, TypeScript, Tailwind CSS v4, Axios

**IA:** OpenAI API

**Reportes:** PDF (reportlab), Excel (openpyxl)

**UX/UI:** Marca **NEXORA** con tema oscuro/claro (tokens `.nx-*` y clase `dark`), set de iconos SVG propio (sin librerías externas).

## Instalación Rápida

### Prerrequisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (o Docker)

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows
pip install -r requirements.txt
cp .env.example .env               # Editar variables
alembic upgrade head
uvicorn app.main:app --reload      # http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                        # http://localhost:5173
```

### 3. Base de Datos (Docker)

```bash
docker compose up -d db
```

O crear la base de datos manualmente en PostgreSQL.

### 4. Primer Administrador

```bash
cd backend

# 1. Crear roles y permisos iniciales (idempotente)
python -m app.cli seed-rbac

# 2. Crear el primer administrador de forma interactiva
#    (solicita username, email, nombre, apellido y contraseña por teclado)
python -m app.cli create-admin
```

Nunca se usan credenciales fijas en el código; la contraseña se pide de forma interactiva y solo se guarda su hash bcrypt.

## Autenticación y Roles

- Login vía `POST /api/auth/login` (formato OAuth2 form-urlencoded) → JWT bearer.
- El JWT contiene únicamente `sub` (id del usuario) y `exp`.
- Autorización RBAC en backend con permisos granulares (`users.read`, `sales.create`, ...).
- Roles: `ADMIN` (todo), `CASHIER` (ventas y POS completos, clientes, abonos de cuentas por cobrar, caja, lectura de catálogo/proveedores/compras), `INVENTORY_MANAGER` (productos, inventario, proveedores, compras, clientes, lectura de ventas, reportes).

## Endpoints Disponibles

| Método | Ruta | Descripción | Permisos |
|--------|------|-------------|----------|
| GET | `/api/health` | Estado del sistema y conexión DB | público |
| GET | `/api/info` | Información de la aplicación | público |
| POST | `/api/auth/login` | Login OAuth2 → JWT | público |
| GET | `/api/auth/me` | Usuario autenticado actual | JWT válido |
| GET | `/api/users` | Listar usuarios | `users.read` |
| GET | `/api/users/{id}` | Obtener usuario | `users.read` |
| POST | `/api/users` | Crear usuario (+ rol) | `users.create` |
| PATCH | `/api/users/{id}` | Actualizar usuario / rol / estado | `users.update` |
| DELETE | `/api/users/{id}` | Desactivar usuario (borrado lógico) | `users.delete` |
| GET | `/api/categories` | Listar categorías | `categories.read` |
| GET | `/api/categories/{id}` | Obtener categoría | `categories.read` |
| POST | `/api/categories` | Crear categoría | `categories.create` |
| PATCH | `/api/categories/{id}` | Actualizar categoría / estado | `categories.update` |
| DELETE | `/api/categories/{id}` | Desactivar categoría (lógico; bloqueada si tiene productos) | `categories.delete` |
| GET | `/api/products` | Listar productos (búsqueda, filtros incl. `supplier_id`, paginación) | `products.read` |
| GET | `/api/products/{id}` | Obtener producto | `products.read` |
| GET | `/api/products/barcode/{barcode}` | Consulta por código de barras (solo activos) | `products.read` |
| POST | `/api/products` | Crear producto | `products.create` |
| PATCH | `/api/products/{id}` | Actualizar producto | `products.update` |
| DELETE | `/api/products/{id}` | Desactivar producto (borrado lógico) | `products.delete` |
| GET | `/api/suppliers` | Listar proveedores (búsqueda, filtros, orden, `{items,total}`) | `suppliers.read` |
| GET | `/api/suppliers/{id}` | Detalle de proveedor (+ cantidad de productos) | `suppliers.read` |
| GET | `/api/suppliers/{id}/products` | Productos del proveedor (paginado) | `suppliers.read` |
| POST | `/api/suppliers` | Crear proveedor | `suppliers.create` |
| PATCH | `/api/suppliers/{id}` | Actualizar proveedor / estado | `suppliers.update` |
| DELETE | `/api/suppliers/{id}` | Desactivar proveedor (borrado lógico, nunca físico) | `suppliers.delete` |
| GET | `/api/inventory/movements` | Historial de movimientos (filtros + paginación) | `inventory.read` |
| GET | `/api/inventory/movements/{id}` | Detalle de movimiento | `inventory.read` |
| GET | `/api/inventory/low-stock` | Productos con stock ≤ mínimo (activos) | `inventory.read` |
| POST | `/api/inventory/entries` | Entrada de stock (+) | `inventory.create` |
| POST | `/api/inventory/exits` | Salida de stock (−; valida disponibilidad) | `inventory.create` |
| POST | `/api/inventory/returns` | Devolución (+) | `inventory.create` |
| POST | `/api/inventory/adjustments` | Ajuste a stock objetivo (motivo obligatorio) | `inventory.update` |
| GET | `/api/purchases` | Listar compras (filtros: proveedor, estado, fechas, número; paginación `{items,total}`) | `purchases.read` |
| GET | `/api/purchases/{id}` | Detalle de compra con ítems (snapshot histórico) | `purchases.read` |
| POST | `/api/purchases` | Crear compra en DRAFT (opcionalmente con ítems) | `purchases.create` |
| PATCH | `/api/purchases/{id}` | Editar encabezado (solo DRAFT) | `purchases.update` |
| DELETE | `/api/purchases/{id}` | Cancelar compra (lógico; nunca físico) | `purchases.cancel` |
| POST | `/api/purchases/{id}/confirm` | Confirmar compra → entrada de inventario transaccional e idempotente | `purchases.confirm` |
| POST | `/api/purchases/{id}/items` | Agregar ítem a compra DRAFT | `purchases.update` |
| PATCH | `/api/purchases/{id}/items/{item_id}` | Modificar ítem (solo DRAFT) | `purchases.update` |
| DELETE | `/api/purchases/{id}/items/{item_id}` | Eliminar ítem (solo DRAFT) | `purchases.update` |
| GET | `/api/customers` | Listar clientes (búsqueda, filtros estado/crédito, orden, `{items,total}`) | `customers.read` |
| GET | `/api/customers/{id}` | Detalle de cliente (+ crédito disponible) | `customers.read` |
| POST | `/api/customers` | Crear cliente | `customers.create` |
| PATCH | `/api/customers/{id}` | Actualizar cliente / crédito (límite ≥ saldo) | `customers.update` |
| DELETE | `/api/customers/{id}` | Desactivar cliente (lógico; historial intacto) | `customers.delete` |
| GET | `/api/customers/{id}/statement` | Estado de cuenta (crédito, cuentas y pagos) | `receivables.read` |
| GET | `/api/receivables` | Listar cuentas por cobrar (filtros cliente/estado/fechas) | `receivables.read` |
| GET | `/api/receivables/{id}` | Detalle de cuenta por cobrar | `receivables.read` |
| GET | `/api/receivables/{id}/payments` | Historial de pagos de la cuenta | `receivables.read` |
| POST | `/api/receivables` | Crear cuenta por cobrar manual (puente hasta ventas) | `receivables.create` |
| POST | `/api/receivables/{id}/payments` | Registrar pago atómico e idempotente (`idempotency_key`) | `receivables.payment` |
| POST | `/api/receivables/{id}/cancel` | Anular cuenta (write-off del saldo restante) | `receivables.cancel` |
| GET | `/api/sales` | Listar ventas (filtros cliente/estado/fechas/número; `{items,total}`) | `sales.read` |
| GET | `/api/sales/{id}` | Detalle de venta con ítems (snapshot histórico de precios) | `sales.read` |
| POST | `/api/sales` | Crear venta en DRAFT (opcionalmente con ítems) | `sales.create` |
| PATCH | `/api/sales/{id}` | Editar encabezado / cliente / pago (solo DRAFT) | `sales.update` |
| DELETE | `/api/sales/{id}` | Cancelar venta (solo DRAFT; nunca físico) | `sales.cancel` |
| POST | `/api/sales/{id}/confirm` | Confirmar venta → salida de stock transaccional; a crédito genera cuenta por cobrar | `sales.confirm` |
| POST | `/api/sales/{id}/items` | Agregar ítem a venta DRAFT (precio snapshot opcional) | `sales.update` |
| PATCH | `/api/sales/{id}/items/{item_id}` | Modificar ítem (solo DRAFT) | `sales.update` |
| DELETE | `/api/sales/{id}/items/{item_id}` | Eliminar ítem (solo DRAFT) | `sales.update` |
| GET | `/api/cash/registers/current` | Caja abierta del usuario actual (`null` si ninguna) | `cash.read` |
| POST | `/api/cash/registers/open` | Abrir turno de caja con monto inicial (único abierto por usuario) | `cash.open` |
| GET | `/api/cash/registers` | Historial de cajas (filtros usuario/estado/fechas) | `cash.read` |
| GET | `/api/cash/registers/{id}` | Detalle de caja + resumen embebido del turno | `cash.read` |
| POST | `/api/cash/registers/{id}/close` | Cerrar caja: fija esperado/contado/diferencia | `cash.close` |
| GET | `/api/cash/registers/{id}/movements` | Movimientos del turno (filtro por tipo) | `cash.movements` |
| GET | `/api/cash/registers/{id}/summary` | Resumen detallado del turno | `cash.report` |
| POST | `/api/cash/movements` | Ingreso/egreso manual con motivo obligatorio | `cash.movements` |
| GET | `/api/reports/{tipo}` | Datos de reporte en JSON (9 tipos; filtros + paginación + totales) | `reports.read` |
| GET | `/api/reports/{tipo}/export` | Exportar reporte a PDF o Excel (`?format=pdf\|excel`; ignora paginación) | `reports.export` |
| GET | `/api/docs` | Documentación Swagger (dev) | — |

## Variables de Entorno

### Backend

| Variable | Descripción | Default |
|----------|------------|---------|
| `DATABASE_URL` | URL de PostgreSQL | `postgresql://postgres:postgres@localhost:5432/sistema_facturacion` |
| `SECRET_KEY` | Clave secreta JWT | `change-this-to-a-strong-random-secret-key` |
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración token | `30` |
| `OPENAI_API_KEY` | Clave API OpenAI | (vacío) |
| `CORS_ORIGINS` | Orígenes CORS | `["http://localhost:5173"]` |
| `APP_ENV` | Entorno | `development` |
| `DEBUG` | Modo debug | `true` |

### Frontend

| Variable | Descripción | Default |
|----------|------------|---------|
| `VITE_API_URL` | URL del backend | `http://localhost:8000/api` |

## Tests

```bash
cd backend
pytest                                    # Todas las pruebas
pytest tests/test_health.py               # Un archivo
pytest tests/test_health.py::test_health_check  # Una función
pytest --cov=app --cov-report=html        # Cobertura
```

## Docker

```bash
# Levantar PostgreSQL + Backend
docker compose up -d

# Ver logs
docker compose logs -f backend

# Detener
docker compose down

# Detener y eliminar datos
docker compose down -v
```

## Desarrollo

Guía completa: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

## Despliegue

| Componente | Plataforma | Notas |
|-----------|-----------|-------|
| Backend | Railway o Render | Ejecutar `alembic upgrade head` en deploy |
| Frontend | Vercel | Build: `npm run build` |
| Base de datos | Railway o Neon | PostgreSQL 15+ |

## Licencia

Proyecto privado.
