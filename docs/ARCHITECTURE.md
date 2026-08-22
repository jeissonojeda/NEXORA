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
| IA | OpenAI API | — |
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
│   ├── components/
│   │   ├── ui/                  # Botones, inputs, modales genéricos
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   └── domain/              # Componentes específicos de dominio
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   └── RegisterPage.tsx
│   │   ├── dashboard/
│   │   │   └── DashboardPage.tsx
│   │   ├── products/
│   │   ├── inventory/
│   │   ├── sales/
│   │   ├── customers/
│   │   ├── suppliers/
│   │   ├── cash-register/
│   │   ├── reports/
│   │   ├── ai/
│   │   └── users/
│   ├── services/                # Llamadas API (Axios)
│   │   ├── api.ts               # Instancia Axios, interceptores
│   │   ├── authService.ts
│   │   ├── productService.ts
│   │   └── ...
│   ├── hooks/                   # Custom hooks
│   │   ├── useAuth.ts
│   │   └── usePagination.ts
│   ├── contexts/
│   │   └── AuthContext.tsx
│   ├── types/                   # Interfaces TypeScript
│   │   └── index.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   └── validators.ts
│   └── routes/
│       ├── AppRouter.tsx
│       └── ProtectedRoute.tsx
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── .env.example
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
- Rutas protegidas que verifican autenticación y rol.
- Layout con sidebar que varía según el rol del usuario.

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
| `entry` | + | Compra, devolución de cliente |
| `sale` | - | Venta realizada |
| `adjustment` | + / - | Corrección de inventario |
| `return` | + | Devolución de venta |
| `purchase` | + | Compra a proveedor |

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

### Tipos de reporte

| Reporte | Filtros | Formatos |
|---------|---------|----------|
| Ventas | fecha, vendedor, método de pago | PDF, Excel |
| Productos vendidos | fecha, categoría | PDF, Excel |
| Inventario | categoría, estado | PDF, Excel |
| Stock bajo | categoría | PDF, Excel |
| Compras | fecha, proveedor | PDF, Excel |
| Caja | fecha, cajero | PDF, Excel |
| Clientes | fecha, cliente | PDF, Excel |
| Utilidades | fecha, período | PDF, Excel |

### Generación

- Backend genera el archivo y lo retorna como respuesta binaria.
- PDF: `reportlab` o `weasyprint`.
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

### Fase 1 — Fundamentos (Semana 1)
- [ ] Configurar proyecto backend (FastAPI, SQLAlchemy, Alembic)
- [ ] Configurar proyecto frontend (React, Vite, TypeScript, Tailwind)
- [ ] Crear migración inicial (users, roles, permissions)
- [ ] Implementar autenticación (login, JWT, registro)
- [ ] Implementar RBAC básico
- [ ] Seed de roles y permisos
- [ ] Configurar `.env.example` y `.gitignore`

### Fase 2 — Catálogos (Semana 2)
- [ ] CRUD completo de productos
- [ ] CRUD de categorías
- [ ] CRUD de proveedores
- [ ] CRUD de clientes
- [ ] Frontend: páginas de catálogos

### Fase 3 — Inventario (Semana 3)
- [ ] Movimientos de inventario (entrada, salida, ajuste, devolución)
- [ ] Actualización automática de stock
- [ ] Alertas de stock bajo
- [ ] Historial de movimientos
- [ ] Frontend: módulo de inventario

### Fase 4 — Ventas y Facturación (Semana 4)
- [ ] Flujo de venta completo (carrito, totales, confirmación)
- [ ] Transacciones de base de datos
- [ ] Generación de facturas
- [ ] Métodos de pago
- [ ] Frontend: punto de venta

### Fase 5 — Caja (Semana 5)
- [ ] Apertura y cierre de caja
- [ ] Movimientos de caja
- [ ] Resumen de turno
- [ ] Frontend: módulo de caja

### Fase 6 — Reportes e IA (Semana 6)
- [ ] Reportes en PDF y Excel
- [ ] Integración OpenAI
- [ ] Análisis de ventas
- [ ] Predicción de demanda
- [ ] Recomendaciones de inventario
- [ ] Resumen inteligente
- [ ] Frontend: dashboard, módulo IA

### Fase 7 — Pulido y Despliegue (Semana 7)
- [ ] Pruebas unitarias e integración
- [ ] Auditoría de operaciones
- [ ] Optimización y seguridad
- [ ] README profesional
- [ ] Despliegue backend (Railway/Render)
- [ ] Despliegue frontend (Vercel)
- [ ] Pruebas finales en producción
