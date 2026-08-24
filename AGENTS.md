# AGENTS.md

## Status

Fase actual: Fase 8 (Caja y Control de Efectivo) completada. Siguiente: Reportes e IA.

## Project intent

Sistema de facturación e inventario con IA para supermercado. Monolito modular: FastAPI backend + React/Vite/TS frontend + PostgreSQL.

## Architecture

Ver `docs/ARCHITECTURE.md` para la documentación completa.

### Estructura clave

```
backend/app/
  core/         → config, security (JWT+bcrypt), rbac, dependencies, exceptions
  db/           → session, base, seed (roles/permisos)
  models/       → SQLAlchemy entities (User, Role, Permission, Supplier, Category, Product, InventoryMovement, Purchase, PurchaseItem, Customer, ReceivableAccount, ReceivablePayment, Sale, SaleItem, CashRegister, CashMovement)
  schemas/      → Pydantic validation
  repositories/ → data access (CRUD base genérico + repos de catálogo/inventario/compras/clientes/cuentas/ventas/caja)
  services/     → business logic (aquí va la magia; InventoryService es el ÚNICO punto de cambio de stock; CustomerCreditService es el ÚNICO punto de cambio del saldo de clientes; CashService es el ÚNICO punto que crea movimientos de caja y calcula efectivo esperado)
  api/routes/   → HTTP endpoints (sin lógica de negocio)
  cli.py        → python -m app.cli (seed-rbac, create-admin)
  ai/           → OpenAI integration
  reports/      → PDF & Excel generation

frontend/src/
  components/   → ui/ (genéricos) + domain/ (específicos)
  pages/        → una carpeta por módulo (auth, categories, suppliers, products, inventory, purchases, customers, sales, cash)
  services/     → Axios calls, una por dominio (api.ts + auth.ts + categories/suppliers/products/inventory/purchases/customers/receivables/sales/cash)
  contexts/     → AuthContext (sesión JWT restaurada desde localStorage)
  hooks/        → custom hooks (useAsync, useHealth)
  types/        → interfaces TypeScript (+ auth.ts, catalog.ts, purchase.ts, customer.ts, sale.ts, cash.ts)
```

## Development commands

```bash
# Backend (desde backend/, con venv activado)
uvicorn app.main:app --reload          # dev server → http://localhost:8000
pytest                                 # tests (SQLite en memoria/archivo, no requiere PG)
pytest tests/test_health.py            # un archivo
pytest tests/test_health.py::test_name # una función
pytest --cov=app --cov-report=html     # cobertura
alembic upgrade head                   # migraciones

# Frontend (desde frontend/)
npm run dev                            # dev server → http://localhost:5173
npm run build                          # typecheck + build producción
npm run lint                           # oxlint

# Docker (raíz del proyecto)
docker compose up -d db                # solo PostgreSQL
docker compose up -d                   # PostgreSQL + backend
docker compose config                  # validar compose
```

## Rules

- Lógica de negocio **solo** en `services/`, nunca en routes.
- Validación de datos con schemas Pydantic, no validaciones manuales.
- Acceso a datos exclusivamente vía repositories + SQLAlchemy.
- Transacciones de DB en operaciones críticas (ventas, inventario, caja).
- Cambios de stock SOLO vía `InventoryService` (nunca `product.stock += n` desde otros módulos).
- Dinero SIEMPRE `Decimal`/`NUMERIC`; nunca float.
- Variables sensibles en `.env`, nunca hardcodeadas.
- No instalar dependencias sin verificar que no exista una alternativa ya en el proyecto.
- Frontend oculta/deshabilita elementos según permisos del usuario.
- Endpoints nuevos se protegen con `Depends(require_permission("dominio.accion"))` (ver `app/core/rbac.py`).
- Nunca devolver `password_hash` ni secretos en respuestas API.
- La autorización SIEMPRE en backend; nunca confiar en datos del frontend.

## Testing

```bash
# Backend (desde backend/, con venv activado)
pytest
pytest tests/test_products.py                    # un archivo
pytest tests/test_products.py::test_name         # una función
pytest --cov=app --cov-report=html               # cobertura
```

Convenciones de tests:
- Fixtures en `conftest.py` para datos comunes.
- Nombres: `test_[función]_[escenario]_[resultado]`.
- Cada test usa rollback al finalizar (DB aislada).
- Datos de prueba con fabricación, no datos reales.
