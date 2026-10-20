# AGENTS.md

## Status

Fases 12 (NEXORA AI Operativo) y 13 (Optimización y Mejoras, incluye asistente IA en español natural + UX) completadas. Sistema de **licenciamiento comercial** implementado (ver `docs/LICENSING.md`).

La Fase 12 convirtió el módulo de IA en un asistente operativo controlado con Google Gemini (tool calling, escaneo de facturas con Gemini Vision, flujo previsualizar/confirmar, idempotencia, auditoría y RBAC). La IA NUNCA modifica datos sin confirmación del usuario; el backend es el punto de control.

Licenciamiento: servicio central propio (`app/licensing/server`, FastAPI + DB separada, Ed25519, panel admin del propietario) + verificación local (`app/licensing/local`, clave pública, migración 0010). El bloqueo por licencia está desactivado salvo producción o `LICENSE_ENFORCEMENT_ENABLED=true`; el backend local es la autoridad, nunca el frontend.

## Project intent

Sistema de facturación e inventario con IA para supermercado. Monolito modular: FastAPI backend + React/Vite/TS frontend + PostgreSQL.

## Architecture

Ver `docs/ARCHITECTURE.md` para la documentación completa.

### Estructura clave

```
backend/app/
  core/         → config, security (JWT+bcrypt), rbac, dependencies, exceptions
  db/           → session, base, seed (roles/permisos)
  models/       → SQLAlchemy entities (User, Role, Permission, Supplier, Category, Product, Tax, Settings, InventoryMovement, Purchase, PurchaseItem, Customer, ReceivableAccount, ReceivablePayment, Sale, SaleItem, CashRegister, CashMovement, AIAnalysis, AIActionHistory, AIInvoiceScan, LocalLicense, LocalInstallation)
  schemas/      → Pydantic validation
  repositories/ → data access (CRUD base genérico + repos de catálogo/inventario/compras/clientes/cuentas/ventas/caja)
  services/     → business logic (aquí va la magia; InventoryService es el ÚNICO punto de cambio de stock; CustomerCreditService es el ÚNICO punto de cambio del saldo de clientes; CashService es el ÚNICO punto que crea movimientos de caja y calcula efectivo esperado; PricingService es el ÚNICO cálculo de precio de venta/utilidad; AIOperationalService es el asistente de IA que ejecuta writes SOLO tras confirmación)
  api/routes/   → HTTP endpoints (sin lógica de negocio)
  licensing/    → núcleo cripto (keys/canonical/documents/errors/constants) + server/ (servicio central FastAPI + DB propia + CLI) + local/ (verificador, huella, servicio local, dependencia require_license)
  cli.py        → python -m app.cli (seed-rbac, create-admin)
  ai/           → Google Gemini (gemini_client, tools, data_gatherer) + Fase 12 client/tools
  reports/      → PDF & Excel generation

frontend/src/
  components/   → ui/ (genéricos: Badge, Button, Modal, PageHeader, KpiCard, LoadingState, EmptyState, ErrorAlert, ConfirmDialog, Pagination, Pagination+, Icon, ThemeToggle, Tooltip) + domain/ (específicos: ProductForm, CategoriesManager, SupplierForm, SuppliersManager, PurchaseBuilder, etc.) + ai/ (AiChatPanel, AiInvoiceScanner, AiActionConfirmModal)
  pages/        → una carpeta por módulo (auth, home, categories, products, inventory, purchases, customers, sales, cash, reports, ai, settings, license). Compras y Proveedores comparten `purchases/ComprasProveedoresPage` (pestañas Registrar compra / Proveedores); Categorías se gestiona con `domain/CategoriesManager` (pestaña dentro de Productos y ruta `/categorias`)
  services/     → Axios calls, una por dominio (api.ts + auth.ts + categories/suppliers/products/inventory/purchases/customers/receivables/sales/cash/reports/ai/aiOperational/settings/license)
  contexts/     → AuthContext (sesión JWT restaurada desde localStorage) + LicenseContext (estado de licencia) + SettingsContext (configuración + moneda) + ThemeContext (dark/light, key `nexora-theme`, clase `dark` en <html>)
  hooks/        → custom hooks (useAsync, useHealth, useDashboard)
  layouts/      → MainLayout (sidebar colapsable/drawer + header con ThemeToggle)
  types/        → interfaces TypeScript (+ auth.ts, catalog.ts, purchase.ts, customer.ts, sale.ts, cash.ts, report.ts, ai.ts, license.ts)
  utils/        → format.ts (formatCurrency) + permissions.ts (userHasPermission)
  routes/       → index.ts (rutas protegidas + rutas AI/providers/settings/license)

Branding: NEXORA. Tema oscuro/claro (Tailwind v4, tokens `.nx-*`, dark mode vía clase). No añadir librerías de iconos: usar el set SVG propio de components/ui/Icon.tsx.
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
