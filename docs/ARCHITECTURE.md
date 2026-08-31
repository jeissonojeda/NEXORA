# Arquitectura — Sistema de Facturación e Inventario con IA

## 1. Arquitectura General

El sistema sigue una arquitectura **monolítica modular** separada en dos componentes principales: un backend API REST y un frontend SPA. La comunicación se realiza mediante HTTP/JSON.

**Principios de diseño:**

- Separación de responsabilidades por capas (API → Servicio → Repositorio → Modelo).
- Lógica de negocio exclusivamente en servicios, nunca en endpoints.
- Validación de datos en schemas (Pydantic).
- Acceso a datos exclusivamente mediante SQLAlchemy.
- Seguridad transversal: JWT, RBAC, validación de entradas.

**Diagrama de capas:**

```
[Frontend React] ←→ [FastAPI Backend] ←→ [PostgreSQL]
                         ↓
                   [OpenAI API]
```

---

## 2. Tecnologías

| Capa | Tecnología | Versión objetivo |
|------|-----------|-----------------|
| Backend | Python + FastAPI | 3.11+ / 0.110+ |
| ORM | SQLAlchemy | 2.0+ |
| Migraciones | Alembic | 1.13+ |
| Base de datos | PostgreSQL | 15+ |
| Autenticación | JWT (python-jose) | — |
| Hashing | bcrypt (passlib) | — |
| Validación | Pydantic v2 | — |
| IA | OpenAI API (análisis) + Google Gemini (asistente operativo) | — |
| Reportes PDF | reportlab o weasyprint | — |
| Reportes Excel | openpyxl | — |
| Frontend | React 18 + Vite + TypeScript | — |
| Router frontend | React Router v6 | — |
| HTTP frontend | Axios | — |
| UI | Tailwind CSS + componentes propios | — |
| Deploy backend | Railway o Render | — |
| Deploy frontend | Vercel | — |

---

## 3. Estructura de Carpetas

### Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Punto de entrada, configuración FastAPI
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Settings, variables de entorno
│   │   ├── security.py          # JWT, hashing, permisos
│   │   └── dependencies.py      # Inyección de dependencias comunes
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py              # Base declarativa SQLAlchemy
│   │   ├── session.py           # Engine y session factory
│   │   └── seed.py              # Seed inicial (roles, permisos)
│   ├── models/                  # Modelos SQLAlchemy
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── permission.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── supplier.py
│   │   ├── customer.py
│   │   ├── inventory.py
│   │   ├── sale.py
│   │   ├── invoice.py
│   │   ├── cash_register.py
│   │   ├── purchase.py
│   │   └── audit.py
│   ├── schemas/                 # Schemas Pydantic
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── product.py
│   │   ├── category.py
│   │   ├── supplier.py
│   │   ├── customer.py
│   │   ├── inventory.py
│   │   ├── sale.py
│   │   ├── invoice.py
│   │   ├── cash_register.py
│   │   ├── purchase.py
│   │   ├── report.py
│   │   └── ai.py
│   ├── repositories/            # Acceso a datos
│   │   ├── __init__.py
│   │   ├── base.py              # CRUD genérico
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── category.py
│   │   ├── supplier.py
│   │   ├── customer.py
│   │   ├── inventory.py
│   │   ├── sale.py
│   │   ├── invoice.py
│   │   ├── cash_register.py
│   │   └── purchase.py
│   ├── services/                # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── category.py
│   │   ├── supplier.py
│   │   ├── customer.py
│   │   ├── inventory.py
│   │   ├── sale.py
│   │   ├── invoice.py
│   │   ├── cash_register.py
│   │   ├── purchase.py
│   │   └── report.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── products.py
│   │       ├── categories.py
│   │       ├── suppliers.py
│   │       ├── customers.py
│   │       ├── inventory.py
│   │       ├── sales.py
│   │       ├── invoices.py
│   │       ├── cash_register.py
│   │       ├── purchases.py
│   │       ├── reports.py
│   │       └── ai.py
│   ├── ai/                      # Integración OpenAI
│   │   ├── __init__.py
│   │   ├── client.py            # Cliente OpenAI
│   │   ├── prompts.py           # Prompts del sistema
│   │   └── analysis.py          # Lógica de análisis
│   └── reports/                 # Generación de reportes
│       ├── __init__.py
│       ├── pdf.py
│       └── excel.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures, cliente de test
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_products.py
│   ├── test_sales.py
│   └── test_inventory.py
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .gitignore
```

### Frontend

```
frontend/
├── src/
│   ├── main.tsx                 # Punto de entrada
│   ├── App.tsx                  # Router principal
│   ├── index.css                # Tailwind v4 + tokens de diseño (.nx-*)
│   ├── components/
│   │   ├── ui/                  # Badge, Button, Modal, PageHeader, KpiCard,
│   │   │                        # LoadingState, EmptyState, ErrorAlert,
│   │   │                        # ConfirmDialog, Pagination, Icon, ThemeToggle
│   │   └── domain/              # Formularios y modales específicos de dominio
│   ├── pages/                   # Una carpeta por módulo:
│   │   ├── auth/                # LoginPage
│   │   ├── home/                # HomePage (dashboard con KPIs + caja)
│   │   ├── products/            # ProductsPage
│   │   ├── inventory/           # InventoryPage
│   │   ├── categories/          # CategoriesPage
│   │   ├── suppliers/           # SuppliersPage
│   │   ├── purchases/           # PurchasesPage + PurchaseDetailPage
│   │   ├── customers/           # CustomersPage + CustomerDetailPage + ReceivablesPage
│   │   ├── sales/               # PointOfSalePage + SalesPage + SaleDetailPage
│   │   ├── cash/                # CashPage
│   │   ├── reports/             # ReportsPage
│   │   └── ai/                  # AIPage
│   ├── layouts/                 # MainLayout (sidebar colapsable/drawer + header)
│   ├── services/                # Llamadas API (Axios), una por dominio
│   │   ├── api.ts               # Instancia Axios, interceptores
│   │   ├── auth.ts
│   │   ├── products.ts
│   │   └── ...
│   ├── hooks/                   # useAsync, useHealth, useDashboard
│   ├── contexts/                # AuthContext (JWT) + ThemeContext (dark/light)
│   ├── types/                   # Interfaces TypeScript por dominio
│   ├── utils/                   # format.ts (formatCurrency) + permissions.ts
│   └── routes/                  # index.ts (rutas protegidas)
├── index.html
├── package.json
└── vite.config.ts               # @tailwindcss/vite (Tailwind v4, sin configs)
```

---

## 4. Arquitectura Backend

El backend está organizado en capas con responsabilidades claras:

### Capa API (routes)
- Recibe peticiones HTTP.
- Valida datos de entrada con schemas Pydantic.
- Llama al servicio correspondiente.
- Retorna respuesta HTTP con formato consistente.
- **No contiene lógica de negocio.**

### Capa de Servicios
- Contiene toda la lógica de negocio.
- Orquesta operaciones entre múltiples repositorios.
- Maneja transacciones de base de datos.
- Valida reglas de negocio.
- Registra en audit log cuando aplica.

### Capa de Repositorios
- Acceso a datos mediante SQLAlchemy.
- Consultas reutilizables.
- Filtrado, paginación, ordenamiento.
- **No contiene lógica de negocio.**

### Capa de Modelos
- Definición de entidades SQLAlchemy.
- Relaciones, restricciones, índices.
- Campos calculados cuando aplica.

### Flujo típico de una petición:

```
HTTP Request → Route → Validation (Schema) → Service → Repository → SQLAlchemy → PostgreSQL
```

### Configuración

`app/core/config.py` carga variables de entorno con Pydantic Settings:

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TIMEOUT: float = 60.0
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    ENVIRONMENT: str = "development"
```

### Conexión a base de datos

- `app/db/session.py` crea el engine y la session factory.
- Se usa `async` si se opta por asyncpg, o síncrono con psycopg2.
- **Decisión:** usar síncrono (psycopg2) por simplicidad inicial. Migrar a async si el rendimiento lo requiere.

---

## 5. Arquitectura Frontend

El frontend es una SPA construida con React + Vite + TypeScript.

### Patrón de componentes

- Componentes funcionales con hooks.
- Separación: UI genérica (`components/ui/`) vs. componentes de dominio (`components/domain/`).
- Páginas orquestan componentes y servicios.

### Estado

- `AuthContext` para estado global de autenticación.
- Estado local con `useState`/`useReducer` para formularios y vistas.
- No se usa state management global extenso (Redux, Zustand) a menos que sea necesario.

### Servicios API

- Una instancia centralizada de Axios (`services/api.ts`).
- Interceptores para attaches JWT automáticamente.
- Cada dominio tiene su archivo de servicio.

### Enrutamiento

- React Router v6.
- Rutas protegidas que verifican autenticación y permiso (`require_permission` en el backend, `userHasPermission` en el frontend).
- `MainLayout` con sidebar colapsable/drawer que varía según el rol del usuario.

### Tema y branding

- Marca **NEXORA** con tema oscuro/claro (`ThemeContext`).
- La preferencia persiste en `localStorage` (key `nexora-theme`); la clase `dark` se aplica en `<html>` junto a tokens de diseño `.nx-*` (Tailwind v4, sin archivos de configuración).
- Iconos: set SVG propio (`components/ui/Icon.tsx`); no se usan librerías de iconos.

---

## 6. Arquitectura de Base de Datos

### Entidades principales

| Entidad | Descripción |
|---------|------------|
| users | Usuarios del sistema |
| roles | Roles (admin, cajero, inventario) |
| permissions | Permisos granulares |
| user_roles | Relación N:N usuarios-roles |
| role_permissions | Relación N:N roles-permisos |
| categories | Categorías de productos |
| products | Productos del catálogo |
| suppliers | Proveedores |
| customers | Clientes |
| inventory_movements | Entradas, salidas, ajustes, devoluciones |
| sales | Cabeceras de venta |
| sale_items | Detalles de venta |
| invoices | Facturas generadas |
| cash_registers | Aperturas de caja |
| cash_movements | Movimientos de caja |
| purchases | Compras a proveedores |
| purchase_items | Detalles de compra |
| customer_créditos | Créditos otorgados a clientes |
| customer_payments | Abonos de clientes |
| ai_analysis | Registros de análisis IA |
| audit_log | Registro de auditoría |

### Conexión

- PostgreSQL 15+.
- URL de conexión por variable de entorno: `DATABASE_URL`.
- Pool de conexiones gestionado por SQLAlchemy.

---

## 7. Relaciones entre Entidades

```
User ──┬── N:N Role (via user_roles)
       └── 1:N AuditLog

Role ──N:N Permission (via role_permissions)

Category ──1:N Product

Supplier ──1:N Product

Customer ──┬── 1:N Sale
           ├── 1:N CustomerCredit
           └── 1:N CustomerPayment

Product ──┬── 1:N SaleItem
          ├── 1:N InventoryMovement
          ├── 1:N PurchaseItem
          └── N:1 Category
          └── N:1 Supplier

Sale ──┬── 1:N SaleItem
       └── 1:1 Invoice

CashRegister ──1:N CashMovement

Sale ──1:N CashMovement

Purchase ──1:N PurchaseItem

InventoryMovement ──N:1 Product
```

### Restricciones clave

- Un producto pertenece a exactamente una categoría.
- Un producto tiene exactamente un proveedor.
- Una venta genera exactamente una factura.
- El stock se actualiza automáticamente al registrar un movimiento de inventario o completar una venta.
- Los montos de crédito y pagos se calculan a partir de las operaciones del cliente.

---

## 8. Sistema de Autenticación

### Flujo de login

1. El usuario envía email + contraseña al endpoint `POST /api/auth/login`.
2. El servicio verifica credenciales (bcrypt).
3. Se genera un JWT con `sub` (user_id), `roles`, `exp`.
4. El token se retorna al frontend.

### Uso del token

- El frontend almacena el JWT en `localStorage` o `httpOnly` cookie.
- Cada petición incluye `Authorization: Bearer <token>`.
- FastAPI extrae y valida el token mediante dependency.

### Refresh / expiración

- Tokens expiran después de `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30 min).
- El frontend redirige a login al recibir 401.

### Registro

- Solo administradores pueden crear usuarios inicialmente.
- Endpoint: `POST /api/auth/register` (requiere rol admin).

---

## 9. Sistema de Roles y Permisos (RBAC)

### Roles iniciales

| Rol | Descripción |
|-----|------------|
| `admin` | Acceso total al sistema |
| `cajero` | Ventas, facturación, clientes, consulta de productos |
| `inventario` | Productos, inventario, proveedores, compras |

### Permisos

Cada operación está mapeada a un permiso (ej: `products:create`, `sales:view`, `inventory:adjust`).

Los permisos se asignan a roles. Al autenticarse, el backend carga los permisos del usuario.

### Enforcement

- En cada route se valida: `require_permission("permiso:accion")`.
- El frontend oculta o deshabilita elementos según permisos del usuario.

### Seed inicial

Al ejecutar `seed.py` se crean los roles y permisos por defecto si no existen.

---

## 10. Flujo de Ventas

```
1. Cajero busca producto (nombre o código de barras)
2. Agrega producto al carrito (cantidad, precio)
3. Modifica cantidades / elimina items
4. Sistema calcula: subtotal, impuestos, descuentos, total
5. Cajero selecciona método de pago
6. Cajero confirma la venta
```

### Al confirmar una venta (transacción única):

```sql
BEGIN;
  INSERT INTO sales (total, tax, discount, payment_method, user_id, customer_id, ...);
  INSERT INTO sale_items (...);
  UPDATE products SET stock = stock - quantity WHERE id = ...;
  INSERT INTO inventory_movements (type='sale', product_id, quantity, ...);
  INSERT INTO cash_movements (type='income', amount, sale_id, ...);
  INSERT INTO invoices (sale_id, ...);
COMMIT;
```

Si cualquier paso falla, se revierte toda la transacción.

---

## 11. Flujo de Inventario

### Tipos de movimiento

| Tipo | Efecto en stock | Descripción |
|------|----------------|------------|
| `ENTRY` | + | Compra confirmada, devolución de cliente, entrada manual |
| `EXIT` | - | Salida manual (merma, venta futura) |
| `ADJUSTMENT` | + / - | Corrección de inventario |
| `RETURN` | + | Devolución |

### Trazabilidad

- Cada movimiento registra: producto, tipo, cantidad, `previous_stock`,
  `new_stock`, fecha, usuario (`created_by`), motivo y referencia opcional
  (`reference_id` + `reference_type`; p. ej. `reference_type='PURCHASE'` con
  el id de la compra que originó la entrada).

### Reglas

- Cada movimiento se registra con: producto, tipo, cantidad, fecha, usuario, motivo.
- El stock se actualiza en la misma transacción del movimiento.
- Si `stock_actual <= stock_minimo`, se genera una alerta visible en el dashboard.
- El historial de movimientos es inmutable (no se editan ni eliminan).

---

## 12. Flujo de Caja

### Ciclo de vida

```
1. Apertura: cajero abre caja con monto inicial
2. Durante turno: se registran ingresos (ventas, abonos) y egresos (gastos, devoluciones)
3. Cierre: cajero cierra caja, sistema genera resumen
```

### Datos del resumen de cierre

- Monto inicial
- Total ingresos
- Total egresos
- Total ventas (efectivo, tarjeta, crédito)
- Monto esperado en caja
- Monto real contado
- Diferencia (sobrante / faltante)
- Fecha y hora de apertura y cierre
- Cajero responsable

### Reglas

- Solo puede haber una caja abierta por cajero a la vez.
- No se pueden registrar ventas sin una caja abierta.
- El cierre genera un reporte con el desglose completo.

---

## 13. Sistema de Reportes

> Implementado en la Fase 9 (ver §21.7 para el detalle vigente). Esta sección
> conserva el diseño original.

### Tipos de reporte

| Reporte | Filtros | Formatos |
|---------|---------|----------|
| Ventas | fecha, vendedor, método de pago | PDF, Excel |
| Productos vendidos | fecha, categoría | PDF, Excel |
| Inventario | categoría, estado | PDF, Excel |
| Stock bajo | categoría | PDF, Excel |
| Compras | fecha, proveedor | PDF, Excel |
| Caja | fecha, cajero | PDF, Excel |
| Clientes con crédito | búsqueda, fechas | PDF, Excel |
| Cuentas por cobrar | cliente, estado, fechas | PDF, Excel |
| Utilidades | fecha, período (día/mes) | PDF, Excel |

### Generación

- Backend genera el archivo y lo retorna como respuesta binaria.
- PDF: `reportlab`.
- Excel: `openpyxl`.
- Headers de descarga: `Content-Disposition: attachment; filename="reporte.pdf"`.

---

## 14. Arquitectura del Módulo IA

### Componentes

- `app/ai/client.py`: Cliente HTTP para OpenAI API.
- `app/ai/prompts.py`: Prompts del sistema para cada tipo de análisis.
- `app/ai/analysis.py`: Orquestación de análisis y almacenamiento de resultados.

### Funcionalidades

#### Análisis de ventas
- Productos más/menos vendidos por período.
- Tendencias de ventas.
- Comparación entre períodos.

#### Predicción de demanda
- Usa datos históricos de ventas.
- Estimación de demanda para los próximos N días.

#### Recomendaciones de inventario
- Productos a reabastecer.
- Cantidad sugerida de compra.
- Productos con riesgo de agotamiento.
- Productos de baja rotación.

#### Resumen inteligente
- Resumen diario de operaciones.
- Alertas importantes.

### Restricciones de seguridad

- La IA **no modifica** directamente la base de datos.
- Las recomendaciones son informativas.
- Las acciones críticas requieren confirmación del usuario.
- Los prompts no deben incluir datos sensibles (contraseñas, tokens).

### Almacenamiento

- Los resultados de análisis se almacenan en la tabla `ai_analysis` para referencia.
- Se cachean resultados recientes para evitar llamadas repetidas.

---

## 15. Seguridad

### Autenticación y autorización
- JWT con expiración configurable.
- Password hashing con bcrypt (mínimo 12 rondas).
- RBAC con permisos granulares.
- Validación de token en cada request protegido.

### Protección de datos
- Variables sensibles en `.env`, nunca en código.
- CORS configurado con orígenes específicos (no `*`).
- HTTPS obligatorio en producción.
- Rate limiting en endpoints de autenticación.

### Validación
- Todos los datos de entrada se validan con Pydantic.
- SQLAlchemy previene SQL Injection.
- Sanitización de inputs.

### Auditoría
- Tabla `audit_log` registra: usuario, acción, entidad, ID, timestamp, datos anteriores/nuevos.
- Las operaciones críticas (ventas, inventario, caja) siempre generan registro de auditoría.

### Cabeceras de seguridad
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (en producción)

---

## 16. Manejo de Errores

### Respuestas estándar del backend

```json
{
  "detail": "Mensaje de error legible",
  "error_code": "PRODUCT_NOT_FOUND",
  "status_code": 404
}
```

### Códigos de error por dominio

| Códigos HTTP | Uso |
|-------------|-----|
| 400 | Solicitud inválida (validación) |
| 401 | No autenticado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 409 | Conflicto (duplicado, estado inválido) |
| 422 | Error de validación (Pydantic) |
| 500 | Error interno del servidor |

### En el frontend

- Axios interceptor maneja errores globalmente.
- Mensajes amigables al usuario.
- Redirección a login en 401.
- Notificaciones toast para errores comunes.

---

## 17. Logging

### Backend

- Python `logging` configurado en `main.py`.
- Logs a archivo en producción, stdout en desarrollo.
- Niveles: DEBUG (dev), INFO (producción), WARNING/ERROR (siempre).
- Información logueada: requests, errores, operaciones críticas, llamadas a IA.

### Formato

```
2024-01-15 10:30:45 - app.api.routes.sales - INFO - Venta #1234 creada por usuario 5
2024-01-15 10:31:02 - app.services.inventory - WARNING - Stock bajo para producto #45
```

### No loguear

- Contraseñas.
- Tokens JWT completos.
- Datos personales sensibles de clientes.

---

## 18. Estrategia de Pruebas

### Tipos

| Tipo | Herramienta | Cobertura objetivo |
|------|------------|-------------------|
| Unitarias | pytest | Servicios, utilidades |
| Integración | pytest + TestClient | Endpoints, repositorios |
| E2E | Cypress o Playwright (futuro) | Flujo completo de venta |

### Organización

```
tests/
├── conftest.py          # Fixtures: DB de test, cliente API, usuario de test
├── test_auth.py
├── test_users.py
├── test_products.py
├── test_categories.py
├── test_suppliers.py
├── test_customers.py
├── test_inventory.py
├── test_sales.py
├── test_cash_register.py
└── test_reports.py
```

### Convenciones

- Cada test usa transacción rollback al finalizar (DB aislada).
- Fixtures en `conftest.py` para datos comunes (usuarios, productos).
- Tests nombrados: `test_[función]_[escenario]_[resultado_esperado]`.
- Datos de prueba con fabricación, no con datos reales.

### Ejecución

```bash
# Todas las pruebas
pytest

# Un archivo
pytest tests/test_products.py

# Una función
pytest tests/test_products.py::test_create_product_success

# Con cobertura
pytest --cov=app --cov-report=html
```

### Frontend (futuro)

- Vitest para unitarias.
- Testing Library para componentes.

---

## 19. Estrategia de Despliegue

### Backend (Railway o Render)

- Desplegable desde GitHub.
- Variables de entorno configuradas en la plataforma.
- Buildpack o Dockerfile para el build.
- Migraciones Alembic se ejecutan en el deploy script.

### Frontend (Vercel)

- Desplegable desde GitHub.
- Build: `npm run build`.
- Variables de entorno en Vercel dashboard.
- SPA con redirección para rutas del cliente.

### Producción

```bash
# Backend
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Frontend
npm run build
```

### Entornos

| Entorno | Backend | Frontend | DB |
|---------|---------|----------|-----|
| Desarrollo | localhost:8000 | localhost:5173 | PostgreSQL local |
| Producción | Railway/Render | Vercel | PostgreSQL (Railway/Neon) |

---

## 20. Variables de Entorno Necesarias

### Backend (`.env`)

```env
# Base de datos
DATABASE_URL=postgresql://user:password@localhost:5432/sistema_db

# JWT
SECRET_KEY=generate-a-strong-random-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI
OPENAI_API_KEY=sk-...

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# Entorno
ENVIRONMENT=development
DEBUG=true

# Reportes
REPORT_OUTPUT_DIR=./reports_output
```

### Frontend (`.env`)

```env
VITE_API_URL=http://localhost:8000/api
```

---

## 21. Plan de Desarrollo por Fases

> **Estado real:** las fases se implementaron con un orden ligeramente distinto al
> plan original (autenticación/RBAC primero, luego catálogo e inventario). El
> detalle vigente está en el README y AGENTS.md.

### Fase 1 — Fundamentos ✅
- [x] Configurar proyecto backend (FastAPI, SQLAlchemy, Alembic)
- [x] Configurar proyecto frontend (React, Vite, TypeScript, Tailwind)
- [x] Crear migración inicial y configuración base
- [x] Health/info endpoints, manejo global de errores
- [x] Configurar `.env.example` y `.gitignore`

### Fase 2 — Autenticación, Usuarios y Roles ✅
- [x] Login OAuth2 form → JWT bearer; `GET /api/auth/me`
- [x] CRUD de usuarios + activación/desactivación lógica
- [x] RBAC completo: roles ADMIN/CASHIER/INVENTORY_MANAGER + 31 permisos granulares
- [x] `Depends(require_permission(...))` en todos los endpoints protegidos
- [x] Seed idempotente vía `python -m app.cli seed-rbac`; admin vía `create-admin`

### Fase 3 — Productos e Inventario ✅
- [x] Categorías: CRUD + desactivación lógica (bloqueada si tiene productos)
- [x] Productos: búsqueda por nombre/código, filtros, paginación `{items,total}`
- [x] Consulta por código de barras (solo activos; único y opcional)
- [x] Movimientos de inventario (entrada, salida, ajuste, devolución)
- [x] Actualización automática y atómica de stock (`SELECT ... FOR UPDATE`)
- [x] CHECK `stock >= 0` a nivel BD como segunda línea de defensa
- [x] Alertas de stock bajo (`GET /api/inventory/low-stock`)
- [x] Historial inmutable con trazabilidad (stock previo/nuevo, usuario, motivo)
- [x] Migración `0002_catalog` (suppliers, categories, products, inventory_movements)
- [x] Frontend: páginas categorías/productos/inventario + login + AuthContext

### Fase 4 — Proveedores ✅
- [x] CRUD completo de proveedores (`/api/suppliers`) con borrado lógico
- [x] Campos de detalle: identificación (única opcional), dirección, ciudad, notas
- [x] Listado con búsqueda (nombre/identificación/email/teléfono), filtro por estado,
      ordenamiento seguro (whitelist) y paginación `{items,total}` con conteo de
      productos por proveedor en una sola consulta (sin N+1)
- [x] `GET /api/suppliers/{id}` con estadística `products_count`
- [x] `GET /api/suppliers/{id}/products` paginado y aislado por proveedor
- [x] Reglas proveedor-producto: producto activo no admite proveedor inexistente (400)
      ni inactivo (409); reactivar producto con proveedor inactivo se rechaza
- [x] RBAC: `suppliers.read/create/update/delete`; CASHIER solo lectura
- [x] Migración `0003_supplier_details` (reversible, sin pérdida de datos)
- [x] Frontend: página `/proveedores` (listado, búsqueda, filtros, detalle modal con
      productos paginados, formulario completo) + selector/filtro de proveedor en productos

### Fase 5 — Compras y Abastecimiento ✅
- [x] Modelo `Purchase` (estados DRAFT/CONFIRMED/CANCELLED) + `PurchaseItem` con snapshot histórico
- [x] Número de compra backend `COMP-YYYY-NNNNNN` único (advisory lock + reintento)
- [x] CRUD `/api/purchases` + gestión de ítems solo en DRAFT; DELETE = cancelación lógica
- [x] Confirmación transaccional única: validaciones + entradas vía `InventoryService`
      (`apply_entry`, sin commits intermedios) + estado CONFIRMED → COMMIT/ROLLBACK atómico
- [x] Idempotencia y concurrencia: reconfirmar devuelve 409; `SELECT ... FOR UPDATE`
      sobre la compra evita dobles confirmaciones simultáneas
- [x] Trazabilidad: movimiento ENTRY con `reference_type='PURCHASE'` y
      `reference_id=purchase.id` (auditoría Compra → Movimiento → Stock)
- [x] Dinero con `Decimal`/`NUMERIC(14,2)`; sin float ni recálculos históricos
- [x] RBAC: `purchases.read/create/update/confirm/cancel`; CASHIER solo lectura
- [x] Migración `0004_purchases` (reversible) + `inventory_movements.reference_type`
- [x] Frontend: `/purchases` (listado con filtros/paginación) y detalle editable
      en DRAFT / solo lectura tras confirmar, con diálogo previo a la confirmación
- [x] Tests: CRUD, ítems, cálculos Decimal, proveedor/producto inválido, confirmación,
      idempotencia, rollback transaccional, estados y RBAC

### Fase 6 — Ventas y Facturación ✅
> Ejecutada como "Fase 7 — Ventas y Facturación" (después de clientes, que
> las ventas requieren para el crédito). Detalle en §21.5.

- [x] Flujo de venta completo (carrito, totales, confirmación)
- [x] Transacciones de base de datos
- [x] Generación de facturas (factura interna: número/fecha/cajero/cliente/
      ítems/totales/pago; integraciones fiscales externas fuera de alcance)
- [x] Métodos de pago
- [x] Frontend: punto de venta

### Fase 7 — Clientes y Créditos ✅
> Ejecutada antes que ventas con el título "Fase 6 — Clientes y Cuentas por
> Cobrar" (las ventas la requieren para el crédito). Detalle en §21.4.

- [x] CRUD de clientes (`/api/customers`) con borrado lógico e historial íntegro
- [x] Identificación única opcional (vacío→NULL; duplicado→409)
- [x] Crédito: `credit_enabled`, `credit_limit`, `current_balance`,
      `credit_available`; límite nunca por debajo del saldo (409)
- [x] Cuentas por cobrar (`receivable_accounts`) OPEN/PARTIALLY_PAID/PAID/CANCELLED
      con invariantes CHECK (`balance = original_amount - paid_amount`, etc.)
- [x] Pagos atómicos con `SELECT ... FOR UPDATE` (cuenta + cliente) vía
      `CustomerCreditService` como ÚNICO punto de cambio de saldo
- [x] Idempotencia de pagos (`idempotency_key` único): repetir NO duplica
- [x] Anulación (write-off del saldo restante conservando pagos históricos)
- [x] Estado de cuenta `GET /api/customers/{id}/statement`
- [x] RBAC: `customers.read/create/update/delete` + `receivables.read/create/
      payment/cancel`; CASHIER cobra pero no crea/anula cuentas ni borra clientes
- [x] Migración `0005_customers_receivables` (reversible)
- [x] Frontend: `/clientes` (listado/formulario) + `/clientes/:id` (estado de
      cuenta, abonos con clave idempotente autogenerada, anulación)
- [x] Tests: 42 nuevos (crédito, pagos, idempotencia, anulación, statement, RBAC)

### Fase 8 — Caja
- [x] Apertura y cierre de caja
- [x] Movimientos de caja
- [x] Resumen de turno
- [x] Integración automática: ventas y abonos generan movimientos de caja
- [x] Frontend: `/caja` (apertura, resumen, movimientos, ingreso/egreso, cierre)
- [x] Tests: 52 nuevos (`tests/test_cash.py`) + E2E HTTP (34 checks)

### Fase 9 — Reportes e IA ✅
- [x] Reportes en PDF y Excel (9 tipos) + vista previa JSON
- [x] Integración OpenAI (`backend/app/ai`)
- [x] Análisis de ventas, predicción de demanda, recomendaciones de inventario
- [x] Dashboard (KPIs) y módulo IA
- [x] Frontend: `/reportes` + `/ia` (rutas protegidas por permiso)

### Fase 10 — IA (módulo de análisis) ✅
- [x] Endpoints de IA en `backend/app/ai` protegidos por RBAC (`ai.*`)
- [x] Página `/ia` del frontend con análisis, tendencias e historial

### Fase 11 — Rediseño UX/UI Profesional (NEXORA) ✅
- [x] Marca **NEXORA** y tema oscuro/claro (`ThemeContext`, key `nexora-theme`,
      clase `dark` en `<html>`, tokens `.nx-*` con Tailwind v4)
- [x] Sistema de componentes UI propio (`components/ui/*`) y set de iconos SVG
      propio (`Icon.tsx`) sin librerías externas
- [x] Rediseño del dashboard (KPIs, incl. "Caja — efectivo esperado"),
      login y todas las páginas de módulos (transiciones, estados de carga,
      tablas responsive con `overflow-x-auto`, Badge por estado)
- [x] `MainLayout` con sidebar colapsable/drawer y ThemeToggle
- [x] Consistencia RBAC en la UI (`utils/permissions.ts`), filtros y
      estados de exportación deshabilitados cuando no hay datos
- [x] Búsqueda con debounce en POS y listado de ventas

### Fase 12 — Pulido y Despliegue (pendiente)
- [ ] Auditoría de operaciones
- [ ] Optimización y seguridad
- [ ] Despliegue backend/frontend

---

## 21.1 Notas de implementación del catálogo e inventario (Fase 3)

Decisiones vigentes que extienden/aclaran este documento:

- **Dinero:** columnas `Numeric(12,2)` / `Decimal` en Python; nunca float. Pydantic
  serializa los montos como string en JSON (ej. `"18.00"`) para evitar errores de
  redondeo en JS; el frontend los formatea con helpers propios.
- **Concurrencia de stock:** cada movimiento hace `SELECT ... FOR UPDATE` sobre la
  fila del producto dentro de la transacción y recalcula stock previo/nuevo desde
  la DB, no desde memoria. SQLite ignora el hint (tests), PostgreSQL lo aplica;
  además existe `CHECK (stock >= 0)` como red de seguridad.
- **Ajustes:** `new_stock` es el valor absoluto objetivo; el delta se calcula en el
  servicio y se rechaza un ajuste sin cambio real (422). Motivo obligatorio.
- **Movimientos inmutables:** no existen endpoints PUT/PATCH/DELETE para
  movimientos; el historial es append-only con trazabilidad completa
  (stock previo/nuevo, usuario creador vía FK `created_by`, motivo, referencia).
- **Borrado lógico:** DELETE de categorías/productos = `is_active=False`. Una
  categoría con productos activos no puede desactivarse (409 `CATEGORY_IN_USE`).
  Los productos inactivos desaparecen de búsquedas por código de barras.
- **Código de barras:** único pero opcional; cadena vacía se normaliza a NULL para
  permitir múltiples productos sin código.
- **Paginación de listados:** categorías retorna array plano; productos y
  movimientos retornan sobre `{items, total}` para paginación en el frontend.
- **Proveedores:** solo el modelo mínimo (id, name, contacto, is_active) quedó en
  la migración `0002_catalog` como dependencia estructural; sin endpoints ni UI
  hasta la fase correspondiente.
- **Permisos nuevos:** `categories.read/create/update/delete`,
  `products.read/create/update/delete`, `inventory.read/create/update`.
  CASHIER tiene lectura de catálogo/inventario (necesario para ventas futuras);
  INVENTORY_MANAGER gestiona todo el dominio; ADMIN todo.

## 21.2 Notas de implementación de proveedores (Fase 4)

Decisiones vigentes que extienden/aclaran este documento:

- **Identificación:** opcional pero única cuando existe (`String(50)`, índice
  único; múltiples NULL permitidos). Sin formato de país impuesto; se normalizan
  cadenas vacías a NULL. Duplicada → 409 `SUPPLIER_IDENTIFICATION_ALREADY_EXISTS`.
- **Nombre:** se conserva la restricción de unicidad heredada de `0002_catalog`
  (mismo criterio que categorías). Duplicado → 409 `SUPPLIER_NAME_ALREADY_EXISTS`.
- **Email:** validado con Pydantic `EmailStr` (dependencia `email-validator`, ya
  presente en requirements). Opcional; inválido → 422.
- **Teléfono:** texto libre (`String(50)`), nunca numérico; admite prefijos,
  espacios, guiones y códigos internacionales.
- **Borrado lógico estricto:** `DELETE /api/suppliers/{id}` solo marca
  `is_active=False`. Nunca hay borrado físico, tenga o no productos asociados;
  la FK `products.supplier_id` usa `ondelete=RESTRICT` como red de seguridad.
- **Regla proveedor-producto:** un producto activo no puede quedar asociado a un
  proveedor inexistente (400 `INVALID_SUPPLIER`) ni inactivo (409
  `SUPPLIER_INACTIVE`). Reactivar un producto cuyo proveedor quedó inactivo se
  rechaza hasta cambiar/quitar el proveedor. Los productos inactivos pueden
  conservar proveedores inactivos (integridad histórica).
- **Listado sin N+1:** el conteo de productos por proveedor del listado se
  resuelve con un LEFT JOIN agregado en una sola consulta.
- **Ordenamiento seguro:** `order_by` limitado por whitelist a
  `name|created_at|updated_at`; `order` a `asc|desc`. Fuera del dominio → 422.
- **Paginación:** proveedores retorna `{items,total}` como productos/movimientos;
  cada ítem incluye `products_count`.
- **Permisos nuevos:** `suppliers.read/create/update/delete`. CASHIER obtiene
  `suppliers.read` (consulta para ventas); INVENTORY_MANAGER CRUD completo;
  ADMIN todo. Ejecutar `python -m app.cli seed-rbac` para sincronizar una base
  existente (seed idempotente agrega permisos/links faltantes).
- **Frontend:** ruta `/proveedores` (convención española del proyecto, la spec
  sugería `/suppliers`); acciones de escritura ocultas sin rol ADMIN/
  INVENTORY_MANAGER; el selector de proveedor en productos carga solo activos
  (límite 100) con filtro por texto client-side.

## 21.3 Notas de implementación de compras (Fase 5)

Decisiones vigentes que extienden/aclaran este documento:

### Modelo y estados

- `Purchase`: `id`, `supplier_id` (RESTRICT), `purchase_number` único, `status`,
  `subtotal/discount/tax/total` (`Numeric(14,2)`), `notes`, `created_by`,
  timestamps y `confirmed_at`. Estados internos estables: `DRAFT`,
  `CONFIRMED`, `CANCELLED` (CHECK en BD).
- `PurchaseItem`: `purchase_id` (CASCADE), `product_id` (RESTRICT),
  `quantity > 0`, `unit_cost >= 0`, `discount/tax/subtotal/total`
  (`Numeric(12,2)`/`(14,2)`). Relación `Purchase 1 ── N PurchaseItem`.
- **Snapshot:** los ítems guardan cantidad/costos/descuentos/impuestos
  históricos; cambiar precios del producto nunca recalcula compras pasadas.
- Un producto no puede repetirse dentro de la misma compra (409).

### Número de compra

- Generado por backend con formato `COMP-YYYY-NNNNNN` (secuencia por año).
- En PostgreSQL se toma `pg_advisory_xact_lock('purchases_number')` antes de
  consultar el último número del año; una colisión residual (IntegrityError
  por UNIQUE) reintenta hasta 5 veces. En SQLite (tests) no hay lock pero el
  lock global de escritura serializa.

### Reglas por estado

| Operación | DRAFT | CONFIRMED | CANCELLED |
|-----------|-------|-----------|-----------|
| Editar encabezado / ítems | ✅ | ❌ 409 | ❌ 409 |
| Agregar/quitar ítems | ✅ | ❌ 409 | ❌ 409 |
| Confirmar | ✅ | ❌ 409 (idempotente) | ❌ 409 |
| Cancelar (DELETE) | ✅ → CANCELLED | ❌ 409 | ❌ 409 |
| Borrado físico | Nunca | Nunca | Nunca |

### Confirmación transaccional

```
BEGIN
  SELECT ... FOR UPDATE sobre la compra (serializa confirmaciones concurrentes)
  validar estado DRAFT + ≥1 item + proveedor activo + productos activos
  para cada item:
      InventoryService.apply_entry(...)   # ENTRY, SIN commit intermedio,
                                          # bloquea fila de producto
      → InventoryMovement(previous_stock, new_stock, created_by,
                          reference_type='PURCHASE', reference_id=purchase.id)
  purchase.status = CONFIRMED; confirmed_at = now()
COMMIT        # ante cualquier excepción → ROLLBACK completo
```

- Todo cambio de stock pasa por `InventoryService` (nunca `product.stock += n`
  desde PurchaseService ni routers). `apply_entry` es el núcleo sin commit que
  participa en la transacción del llamador; `add_stock` lo reutiliza y confirma.
- **Idempotencia:** si la compra ya está CONFIRMED el endpoint responde
  409 `PURCHASE_ALREADY_CONFIRMED` sin tocar stock (confirmar dos veces no
  duplica entradas).
- **Rollback probado:** si cualquier `apply_entry` falla a mitad de la compra,
  la compra queda DRAFT, el stock no cambia y no quedan movimientos parciales.
- El proveedor debe existir y estar activo al crear Y al confirmar; los
  productos también deben existir y estar activos.
- No se modifica `Product.sale_price` ni `Product.purchase_price` al confirmar:
  los precios comerciales pertenecen al módulo de productos (decisión
  documentada; el costo histórico vive en `PurchaseItem.unit_cost`).

### Cálculos (Decimal, redondeo ROUND_HALF_UP a 2 decimales)

```
item_subtotal = quantity × unit_cost
item_total    = item_subtotal - item_discount + item_tax
purchase.subtotal = Σ item_subtotal
purchase.total    = purchase.subtotal - purchase_discount + purchase_tax
```

Descuento (ítem o encabezado) mayor que el subtotal → 422.

### API

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/api/purchases` | Filtros `supplier_id`, `status`, `date_from`, `date_to`, `q` (número); paginación `{items,total}`; proveedor precargado con JOIN (sin N+1) |
| GET | `/api/purchases/{id}` | Detalle con ítems + nombre producto/proveedor/usuario |
| POST | `/api/purchases` | Crea DRAFT (ítems opcionales); 201 |
| PATCH | `/api/purchases/{id}` | Solo DRAFT: proveedor, notas, descuento, impuesto |
| DELETE | `/api/purchases/{id}` | Cancelación lógica → CANCELLED; 204 |
| POST | `/api/purchases/{id}/confirm` | Transaccional + idempotente; 200 |
| POST/PATCH/DELETE | `/api/purchases/{id}/items[/{item_id}]` | Solo DRAFT |

Errores: 404 `PURCHASE_NOT_FOUND` / `PURCHASE_ITEM_NOT_FOUND` /
`SUPPLIER_NOT_FOUND` / `PRODUCT_NOT_FOUND`; 409 `PURCHASE_ALREADY_CONFIRMED`,
`PURCHASE_CANCELLED`, `SUPPLIER_INACTIVE`, `PRODUCT_INACTIVE`,
`PURCHASE_ITEM_DUPLICATE_PRODUCT`; 422 `PURCHASE_EMPTY`,
`ITEM_DISCOUNT_EXCEEDS_SUBTOTAL`, `DISCOUNT_EXCEEDS_SUBTOTAL`.

### RBAC

- Permisos nuevos: `purchases.read/create/update/confirm/cancel`.
- ADMIN: todo. INVENTORY_MANAGER: ciclo completo (crear/editar/confirmar/cancelar).
- CASHIER: solo `purchases.read` (no puede crear, editar, confirmar ni cancelar).
- Tras actualizar desde una versión anterior ejecutar
  `python -m app.cli seed-rbac` (seed idempotente).

### Frontend

- Ruta `/purchases` (listado: número, proveedor, fecha, estado, total, acciones;
  filtros por estado, proveedor y rango de fechas; paginación) y
  `/purchases/:id` (detalle).
- Crear compra = elegir proveedor activo → guardar borrador → agregar productos
  con cantidad/costo/descuento/impuesto → ver subtotal/descuento/impuesto/total.
- DRAFT muestra acciones (editar encabezado, agregar/editar/eliminar producto,
  confirmar, cancelar); CONFIRMED/CANCELLED es solo lectura.
- Confirmar exige diálogo explícito ("se actualizará el inventario... ya no
  podrá editarse"); tras confirmar la UI recarga y refleja el stock nuevo.
- Tipos en `types/purchase.ts`; llamadas HTTP en `services/purchases.ts`.

## 21.4 Notas de implementación de clientes y cuentas por cobrar (Fase 6)

Decisiones vigentes que extienden/aclaran este documento:

### Modelo

- `Customer`: `identification` única **opcional** (vacío/espacios → NULL;
  duplicado → 409), `name`, contacto opcional, `is_active`,
  `credit_enabled` (default false), `credit_limit >= 0`,
  `current_balance >= 0`. CHECK: si `credit_enabled`, entonces
  `current_balance <= credit_limit`. Propiedad `credit_available`
  (nunca negativa, siempre escala 2; 0.00 sin crédito).
- `ReceivableAccount`: `customer_id` (RESTRICT), `reference_type`
  MANUAL/SALE (SALE reservado para el módulo de ventas), `description`,
  `original_amount > 0`, `paid_amount >= 0`, `balance = original_amount -
  paid_amount` (CHECK), `due_date`, estado OPEN/PARTIALLY_PAID/PAID/CANCELLED
  (CHECK). Los pagos son historial inmutable.
- `ReceivablePayment`: `amount > 0`, método CASH/CARD/TRANSFER/OTHER (CHECK),
  `reference`, `notes`, `created_by`; `idempotency_key` String(100) **única
  nullable** como red de seguridad contra carreras.

### CustomerCreditService (guardarraíles del crédito)

- Es el ÚNICO componente que modifica `current_balance`
  (`increase_balance`/`decrease_balance`); asume fila bloqueada FOR UPDATE por
  el llamador y no hace commit (compone transacciones).
- `ensure_can_assume_debt`: exige cliente activo + crédito habilitado +
  saldo proyectado ≤ límite; si falla → 409 `CUSTOMER_INACTIVE`,
  `CREDIT_NOT_ENABLED`, `CREDIT_LIMIT_EXCEEDED`.
- `decrease_balance` garantiza saldo nunca negativo (409).

### Pagos (transacción + idempotencia)

```
si idempotency_key existe en BD → devolver pago original SIN mover nada (200)
BEGIN
  SELECT ... FOR UPDATE cuenta   (y re-chequeo de la clave bajo lock)
  validar estado OPEN/PARTIALLY_PAID y monto ≤ balance (409)
  SELECT ... FOR UPDATE cliente
  INSERT payment; paid_amount += monto; balance = original - paid;
      status = PAID | PARTIALLY_PAID
  CustomerCreditService.decrease_balance(cliente, monto)
COMMIT        # ante cualquier excepción → ROLLBACK completo
```

- Repetir un pago con la misma clave responde 200 con el pago original
  (creación → 201); nunca se aplica dos veces. Sin clave cada pago es válido.
- Anulación (`POST /receivables/{id}/cancel`): solo OPEN/PARTIALLY_PAID;
  descuenta el saldo restante del cliente (write-off) conservando los abonos
  como historial; la cuenta CANCELLED conserva su `balance` a modo de registro.

### API

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/api/customers` | Búsqueda (nombre/identif./email/tel.), filtros `is_active`/`credit_enabled`, orden whitelist, `{items,total}` |
| GET | `/api/customers/{id}` | Incluye `credit_available` |
| POST/PATCH | `/api/customers[/{id}]` | Límite nunca bajo el saldo (409); habilitar crédito exige límite > 0 (422) |
| DELETE | `/api/customers/{id}` | Desactivación lógica; historial intacto |
| GET | `/api/customers/{id}/statement` | Crédito + conteos por estado + `total_balance` + cuentas y pagos paginados |
| GET/POST | `/api/receivables` | POST es puente administrativo hasta ventas (`receivables.create`) |
| GET | `/api/receivables/{id}` y `/{id}/payments` | Detalle e historial de pagos |
| POST | `/api/receivables/{id}/payments` | Atómico + idempotente; 201 creado / 200 replay |
| POST | `/api/receivables/{id}/cancel` | Write-off del saldo restante |

Errores: 404 `CUSTOMER_NOT_FOUND` / `RECEIVABLE_NOT_FOUND`;
409 `CUSTOMER_IDENTIFICATION_ALREADY_EXISTS`, `CREDIT_LIMIT_BELOW_BALANCE`,
`CREDIT_LIMIT_EXCEEDED`, `CREDIT_NOT_ENABLED`, `CUSTOMER_INACTIVE`,
`PAYMENT_EXCEEDS_BALANCE`, `RECEIVABLE_ALREADY_PAID`, `RECEIVABLE_CANCELLED`,
`RECEIVABLE_ALREADY_CANCELLED`.

### RBAC y frontend

- Permisos nuevos: `customers.delete`, `receivables.read/create/payment/cancel`.
- ADMIN todo; INVENTORY_MANAGER gestiona clientes (sin delete ni receivables);
  CASHIER lee clientes y registra pagos, pero no crea/anula cuentas ni borra
  clientes. Ejecutar `python -m app.cli seed-rbac` tras actualizar.
- Frontend: `/clientes` (listado con búsqueda/filtros, formulario con sección
  de crédito) y `/clientes/:id` (tarjetas de crédito/deuda, cuentas con
  acciones Abonar/Anular según permisos, historial de pagos). El modal de
  abono autogenera una `idempotency_key` estable por intento (UUID): un
  reintento tras error de red jamás cobra dos veces.
- Tipos en `types/customer.ts`; HTTP en `services/customers.ts` y
  `services/receivables.ts`.

## 21.5 Notas de implementación de ventas y facturación (Fase 7)

> Ejecutada después de clientes (plan-Fase 7) y antes de caja; corresponde al
> plan-Fase 6 del documento original.

### Modelo

- `sales` + `sale_items` (migración `0006_sales`, reversible). Estados
  `DRAFT → CONFIRMED | CANCELLED` con CHECKs; solo DRAFT es editable/cancelable
  y CONFIRMED es inmutable (igual que compras).
- Numeración `VTA-YYYY-NNNNNN` con `pg_advisory_xact_lock('sales_number')` +
  reintento ante `IntegrityError` (patrón de compras).
- Cliente opcional (venta anónima / consumidor final); obligatorio para
  `CREDIT`. Métodos de pago: `CASH/CARD/TRANSFER/CREDIT` (CHECK extensible).
- `unit_price` de cada ítem es **snapshot** histórico: cambiar
  `Product.sale_price` nunca recalcula ventas pasadas.
- Dinero siempre `Decimal`/NUMERIC (14,2 cabecera, 12,2 ítems), ROUND_HALF_UP.

### Confirmación transaccional

Único COMMIT por confirmación (`SaleService.confirm_sale`): bloqueo de fila
(`SELECT ... FOR UPDATE`) → validaciones (productos activos, venta no vacía,
idempotencia) → salidas de stock vía `InventoryService.apply_exit`
(movimiento EXIT con `reference_type='SALE'`, `reference_id=sale.id`, sin
commits intermedios) → normalización de pago → si CREDIT, creación de la
cuenta por cobrar vía `ReceivableService.create_receivable_in_transaction`
(núcleo sin commit reutilizado también por el método público) → estado
CONFIRMED + timestamp. Cualquier fallo (stock insuficiente, cupo excedido)
ejecuta ROLLBACK completo: ni stock ni saldo del cliente quedan tocados.

### Pagos

- CASH: sin registro de efectivo se asume pago exacto; con monto registrado,
  exige `amount_paid ≥ total` (422 `PAYMENT_INSUFFICIENT`) y calcula vuelto.
- CARD/TRANSFER: registran `amount_paid = total`, vuelto 0.
- CREDIT: `amount_paid = 0`; exige cliente activo con crédito habilitado y
  cupo suficiente (validado bajo lock por `CustomerCreditService`). El cobro
  real ocurre cuando el cliente abone la cuenta generada.

### API

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/api/sales` | Filtros cliente/estado/fechas/número; `{items,total}` |
| GET | `/api/sales/{id}` | Detalle con ítems (snapshot) |
| POST | `/api/sales` | DRAFT con ítems opcionales; snapshot de precio automático |
| PATCH | `/api/sales/{id}` | Encabezado/cliente/pago (solo DRAFT); valida pareja método-cliente |
| DELETE | `/api/sales/{id}` | Cancelar (solo DRAFT) |
| POST | `/api/sales/{id}/confirm` | Transacción completa descrita arriba |
| POST/PATCH/DELETE | `/api/sales/{id}/items[/{item_id}]` | Carrito en DRAFT |

Errores: 404 `SALE_NOT_FOUND` / `SALE_ITEM_NOT_FOUND` / `PRODUCT_NOT_FOUND` /
`CUSTOMER_NOT_FOUND`; 409 `PRODUCT_INACTIVE`, `CUSTOMER_INACTIVE`,
`CREDIT_NOT_ENABLED`, `CREDIT_LIMIT_EXCEEDED`, `SALE_ITEM_DUPLICATE_PRODUCT`,
`SALE_ALREADY_CONFIRMED`, `SALE_ALREADY_CANCELLED`, `SALE_CANCELLED`,
`SALE_NUMBER_GENERATION_FAILED`; 422 `SALE_EMPTY`, `PAYMENT_INSUFFICIENT`,
`CUSTOMER_REQUIRED_FOR_CREDIT`, `DISCOUNT_EXCEEDS_SUBTOTAL`,
`ITEM_DISCOUNT_EXCEEDS_SUBTOTAL`.

### RBAC y frontend

- Permisos nuevos: `sales.update/confirm/cancel` (+ existentes
  `sales.read/create`). ADMIN todo; CASHIER opera el POS completo;
  INVENTORY_MANAGER solo consulta historial.
- Frontend: `/ventas` (historial con filtros), `/pos` (búsqueda por nombre o
  código de barras, carrito con control de stock disponible, cliente opcional
  con crédito visible, métodos de pago, vuelto estimado, cobro = crear +
  confirmar) y `/ventas/:id` (comprobante con acciones según estado).
- Tipos en `types/sale.ts`; HTTP en `services/sales.ts`.
- Tests: 53 nuevos (`tests/test_sales.py`) cubriendo snapshot, carrito,
  confirmación/movimientos, idempotencia, rollbacks (stock y crédito),
  pagos, integración con cuentas por cobrar y RBAC.

## 21.6 Notas de implementación de caja y control de efectivo (Fase 8)

> Ejecutada después de ventas (plan-Fase 8) como módulo transversal que
> registra el flujo de efectivo generado por las fases anteriores.

### Modelo

- `cash_registers` + `cash_movements` (migración `0007_cash`, reversible).
  Estados de caja `OPEN → CLOSED | CANCELLED` con CHECKs; montos
  `Numeric(12..14,2)` siempre en `Decimal`.
- **Un turno abierto por cajero:** índice parcial único sobre
  `cash_registers(user_id) WHERE status = 'OPEN'`
  (`sqlite_where` / `postgresql_where`). La carrera entre dos aperturas
  simultáneas se resuelve con re-chequeo tras capturar `IntegrityError`.
- Movimientos `OPENING | SALE | RECEIVABLE_PAYMENT | CASH_IN | CASH_OUT |
  ADJUSTMENT` (ADJUSTMENT reservado, no expuesto por API). Montos positivos
  (CHECK permite `amount = 0` solo para OPENING); medio de pago
  `CASH/CARD/TRANSFER` opcional.
- **Idempotencia por referencia:** índice parcial único
  `(reference_type, reference_id) WHERE reference_id IS NOT NULL`; una venta o
  un abono genera a lo sumo un movimiento aunque el hook se invoque dos veces.

### Regla de efectivo centralizada

Función única `cash_delta(type, method)` (fuente de verdad): OPENING/CASH_IN →
+1; CASH_OUT → −1; SALE y RECEIVABLE_PAYMENT → +1 solo si el medio es CASH;
CARD/TRANSFER registran trazabilidad sin tocar el efectivo; ADJUSTMENT → 0.
El efectivo esperado del turno es la suma de efectos; se recalcula con un
agregado `GROUP BY (type, method)` portable (sin N+1).

### Integración automática (backward-compatible)

- `SaleService.confirm_sale` invoca
  `CashService.record_sale_movement_in_transaction(...)` justo antes de su
  COMMIT: si el confirmador tiene caja abierta queda trazado el movimiento
  SALE; si no hay caja abierta (o la venta es CREDIT / total 0) es no-op sin
  afectar la transacción de la venta.
- `ReceivableService.register_payment` invoca
  `record_receivable_payment_movement_in_transaction(...)` después de bajar el
  saldo del cliente y antes del COMMIT; la clave de idempotencia del pago
  garantiza que repetirlo no duplique el movimiento de caja.
- Ningún hook hace commit propio: respetan la transacción del servicio origen.

### Cierre

Único COMMIT (`close_register`): bloqueo FOR UPDATE → validaciones de estado →
cálculo del esperado → fijación de `expected_amount`, `counted_amount`,
`difference`, `closed_at`, `closed_by_id` → estado CLOSED. La diferencia puede
ser negativa (faltante), positiva (sobrante) o cero (cuadrado). Tras cerrar,
la consulta "caja actual" devuelve null y el usuario puede abrir un nuevo
turno; los montos del resumen de una caja cerrada quedan congelados.

### API

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/api/cash/registers/current` | Caja abierta del usuario (null si ninguna); resumen embebido |
| POST | `/api/cash/registers/open` | 201; apertura única por usuario (409 REGISTER_ALREADY_OPEN) |
| GET | `/api/cash/registers` | Historial con filtros user/status/fechas |
| GET | `/api/cash/registers/{id}` | Detalle + resumen |
| POST | `/api/cash/registers/{id}/close` | Cierra y congela esperado/contado/diferencia |
| GET | `/api/cash/registers/{id}/movements` | Filtro opcional por tipo |
| GET | `/api/cash/registers/{id}/summary` | Requiere `cash.report` (solo ADMIN) |
| POST | `/api/cash/movements` | Solo CASH_IN/CASH_OUT con motivo ≥3 caracteres |

Errores: 404 `REGISTER_NOT_FOUND`; 409 `REGISTER_ALREADY_OPEN`,
`REGISTER_ALREADY_CLOSED`, `REGISTER_CANCELLED`, `REGISTER_NOT_OPEN`,
`INSUFFICIENT_CASH` (egreso > efectivo disponible),
`INVALID_REGISTER_STATUS`, `INVALID_MOVEMENT_TYPE`.

### RBAC y frontend

- Permisos existentes `cash.read/open/close/movements` (ADMIN + CASHIER);
  nuevo `cash.report` solo ADMIN. INVENTORY_MANAGER no maneja efectivo (403
  en todo el dominio caja). Seed idempotente crea el permiso nuevo.
- Frontend `/caja`: estado sin-caja → formulario de apertura; dashboard con
  tarjetas de resumen (apertura, ventas efectivo, abonos, ingresos, egresos,
  medios electrónicos, esperado destacado), tabla de movimientos paginada,
  modales de ingreso/egreso y cierre con vista previa de diferencia
  (advertencias de faltante/sobrante) e historial de turnos cerrados.
- Tipos en `types/cash.ts`; HTTP en `services/cash.ts`.
- Tests: 52 nuevos (`tests/test_cash.py`) + guion E2E HTTP real
  (33 checks: apertura→ventas→abonos→ingresos/egresos→cierre→historial,
  más RBAC e idempotencia de replay) contra uvicorn con SQLite temporal.

## 21.7 Notas de implementación de reportes y exportación (Fase 9)

> Módulo de solo lectura: no agrega tablas ni migraciones; consulta los datos
> generados por las fases anteriores a través de un repositorio dedicado.

### Alcance

Nueve reportes (`sales`, `products-sold`, `inventory`, `low-stock`,
`purchases`, `cash-registers`, `customers-credit`, `receivables`,
`utilities`) disponibles como JSON (vista previa) y como archivo PDF/Excel.
El módulo de IA queda pendiente para la siguiente fase.

### Arquitectura

- `repositories/report_repository.py`: único acceso a datos del dominio;
  consultas agregadas SQL (SUM/CASE/GROUP BY) que **nunca** mutan estado.
- `services/report_service.py`: lógica de negocio — registro de tipos de
  reporte (`REPORT_DEFINITIONS`), validación de filtros aplicables por tipo,
  construcción de columnas/filas/totales y delegación a los renderizadores.
- `reports/pdf.py` / `reports/excel.py`: render puro (reportlab /
  openpyxl); reciben título, encabezados, filas, totales, filtros aplicados,
  notas y nombre de archivo sugerido. Sin lógica de negocio.
- `api/routes/reports.py`: dos endpoints sin lógica:
  `GET /api/reports/{tipo}` (`reports.read`) y
  `GET /api/reports/{tipo}/export?format=pdf|excel` (`reports.export`).
- Esquema de respuesta genérico (`ReportDataResponse`): `report_type`,
  `title`, `generated_at`, `filters_applied`, `columns`
  (`{key,label,type}` con tipo `text|money|int|datetime|date`), `items`
  (filas como diccionarios), paginación `skip/limit/total` y `totals`.

### Reglas de negocio

- **Totales sobre el conjunto completo:** los totales se calculan en SQL
  sobre TODAS las filas del filtro; la paginación (`skip`/`limit`) solo
  recorta la página mostrada. Las exportaciones ignoran la paginación e
  incluyen todas las filas.
- **Ventas/compras confirmadas:** `sales`, `products-sold` y `utilities`
  excluyen borradores/canceladas (estado CONFIRMED). Compras incluye
  DRAFT/CONFIRMED/CANCELLED filtrable por estado.
- **Utilidades = aproximación:** `utilidad = ingresos − cantidad_vendida ×
  precio_de_compra_ACTUAL_del_producto`; los ítems de venta no guardan
  snapshot del costo, por lo que el resultado es estimado si el costo cambió
  después de vender. Agrupación por día o mes (default mensual) usando la
  fecha efectiva de venta (`COALESCE(confirmed_at, created_at)`). El reporte
  incluye una nota visible explicando la aproximación.
- **Clientes con crédito:** solo clientes `credit_enabled=True`;
  `current_balance` es el saldo corriente del cliente y
  `receivable_balance` suma cuentas OPEN/PARTIALLY_PAID.
- **Inventario valorizado:** valor a costo (`stock × purchase_price`) y a
  precio de venta (`stock × sale_price`); filtro por categoría y estado
  activo/inactivo. Stock bajo lista productos activos con
  `stock ≤ minimum_stock` ordenados por faltante descendente.

### Validaciones y errores

- Tipo de reporte inexistente → 404 `REPORT_NOT_FOUND`.
- Filtro no aplicable al reporte → 422 `INVALID_FILTER_FOR_REPORT`.
- Valor inválido para un enum (método de pago, estados, período) →
  422 `INVALID_FILTER_VALUE`.
- `date_from > date_to` → 422 `INVALID_DATE_RANGE`.
- Formato de exportación distinto de pdf/excel → 422 `INVALID_EXPORT_FORMAT`.

### RBAC y frontend

- Permisos ya existentes en el seed: `reports.read` y `reports.export`
  (ADMIN + INVENTORY_MANAGER). CASHIER obtiene 403 en ambos endpoints;
  el nav "Reportes" se oculta según roles.
- Frontend `/reportes`: selector de tipo, formularios de filtro dinámicos
  por reporte (el filtro de vendedor/cajero solo aparece para ADMIN porque
  listar usuarios requiere `users.read`), tabla genérica construida desde
  `columns` con fila TOTALES y paginación, botones de exportación que
  descargan el blob respetando el filename de `Content-Disposition`.
- Tipos en `types/report.ts`; HTTP en `services/reports.ts`.
- Tests: 57 nuevos (`tests/test_reports.py`): RBAC, validaciones, filas y
  totales de los 9 reportes, filtros, paginación, reportes vacíos y
  exportación real (magic bytes `%PDF`/`PK`, content-types, nombres
   `reporte-{tipo}-{fecha}-{hora}.pdf|xlsx`, introspección del xlsx vía
   openpyxl, exportación completa ignora límite de página).

## 8. Fase 12 — NEXORA AI Operativo

### Objetivo

Convertir el módulo de IA en un **asistente operativo controlado** usando
Google Gemini. El backend es el punto de control: la IA puede *leer* datos del
negocio libremente, pero **jamás ejecuta una escritura** sin la confirmación
explícita del usuario (flujo previsualizar → confirmar).

### Componentes backend

- `app/ai/gemini_client.py` — cliente Google `google-genai` (API v2 snake_case),
  `GeminiClient` (genera respuestas de texto, *function calling* y *vision*),
  `GeminiClientError` y el singleton `gemini_client`. Config vía env:
  `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_MAX_TOKENS`, `GEMINI_TIMEOUT`.
- `app/ai/tools.py` — registro declarativo de herramientas:
  - `READ_TOOLS` (5): `search_products`, `get_low_stock`, `get_business_context`,
    `search_suppliers`, `get_stock_health` — se ejecutan de inmediato (solo lectura).
  - `ACTION_TOOLS` (5): `create_purchase`, `adjust_inventory`, `create_product`,
    `create_supplier`, `register_payment` — **interceptados** en el chat; nunca se
    ejecutan sin confirmación. Cada una declara su `permission` (ai.*) y su
    `action_type` (→ permiso nativo del dominio).
- `app/services/ai_operational_service.py` — `AIOperationalService`:
  - `chat()`: bucle de *tool calling* (tope `MAX_TOOL_ITERATIONS=5`). Las tools
    de lectura se ejecutan y se retroalimentan; las de acción se capturan como
    `ActionProposal` y se devuelven con el texto final, sin ejecutarlas.
  - `preview_action()` / `confirm_action()`: escrituras seguras, **idempotentes**
    (por `idempotency_key`) y **auditadas** (tabla `ai_action_history`). Los writes
    se delegan en los servicios de dominio (PurchaseService, InventoryService,
    ProductService, SupplierService, ReceivableService) para respetar las reglas
    de stock/caja/saldo.
  - `scan_invoice()`: envía la imagen/PDF a Gemini Vision, parsea JSON tolerando
    texto, hace *matching* contra proveedores/productos del catálogo y detecta
    duplicados por proveedor+número.
- Modelos: `AIActionHistory` (auditoría, estados PREVIEW/CONFIRMED/REJECTED/FAILED)
  y `AIInvoiceScan`. Migración: `alembic/versions/a1b2c3d4e5f6_0009_ai_operational.py`.

### Endpoints

| Método/URI | Descripción | Permiso |
|---|---|---|
| `POST /api/ai/chat` | Chat con tool calling (devuelve propuestas) | `ai.read` |
| `POST /api/ai/invoice/scan` | Escaneo de factura (multipart file) | `ai.invoice` |
| `POST /api/ai/action/preview` | Validar/previsualizar una acción | `ai.execute` |
| `POST /api/ai/action/confirm` | Ejecutar la acción (idempotente+auditado) | `ai.execute` |
| `GET /api/ai/history` | Historial de auditoría de acciones | `ai.read` |
| `GET /api/ai/health` | Disponibilidad de Gemini | `ai.read` |
| `GET /api/ai/tools` | Catálogo de herramientas | `ai.read` |

### Seguridad (defensa en profundidad)

- RBAC: ADMIN=all; INVENTORY_MANAGER=`ai.read`,`ai.analyze`,`ai.invoice`,
  `ai.inventory`,`ai.purchase`,`ai.execute`; CASHIER=`ai.read`,`ai.analyze`
  (sin escalada).
- Al confirmar, se exige en el servicio el `permission` de la acción **y** el
  permiso nativo de su `action_type` (p. ej. `purchase`→`PURCHASES_CREATE`).
- `GeminiClientError` en `/chat` se traduce a `502 AI_API_ERROR` (nunca 500).
- La clave API de Gemini vive solo en `.env`; no se loguea ni se expone en HTTP.

### Frontend

- `services/aiOperational.ts`: chatAi, scanInvoice (FormData), previewAction,
  confirmAction, getAiHistory, getAiHealth, getAiTools.
- `types/ai.ts`: tipos operativos (chat, propuestas, escaneo, historial).
- `components/ai/`: `AiChatPanel`, `AiInvoiceScanner`, `AiActionConfirmModal`.
- `pages/ai/AIPage.tsx`: pestañas nuevas **Asistente** y **Escaneo de facturas**;
  los botones de confirmación de acciones solo aparecen con `ai.execute`.

### Tests

- `tests/test_ai_tools.py`, `tests/test_ai_permissions.py`,
  `tests/test_ai_operational.py` (chat con fake client, confirm de compra
  transaccional + stock, idempotencia por clave, fallo auditado),
  `tests/test_ai_invoice.py` (parseo Gemini, matching, duplicados, tipo no
  soportado, JSON no válido). Usan `tests/fakes.py` (`FakeGeminiClient`).
