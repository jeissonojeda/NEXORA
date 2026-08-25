# Guía de Desarrollo

## Prerrequisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker (opcional, para PostgreSQL)

## Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd sistema-facturacion-inventario-ia
```

### 2. Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores
```

### 3. Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env
```

## Base de Datos

### Opción 1: Docker (recomendado)

```bash
docker compose up -d db
```

Esto inicia PostgreSQL en el puerto 5432.

### Opción 2: PostgreSQL local

Crear la base de datos manualmente:

```sql
CREATE DATABASE sistema_facturacion;
```

### Configurar conexión

Editar `backend/.env`:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sistema_facturacion
```

### Ejecutar migraciones

```bash
cd backend
alembic upgrade head
```

### Crear migración (cuando haya cambios en modelos)

```bash
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head
```

Verificar reversibilidad de una migración:

```bash
$env:DATABASE_URL='sqlite:///./migration_check.db'   # Windows PowerShell
alembic upgrade head
alembic downgrade base
alembic upgrade head
Remove-Item migration_check.db
```

## Autenticación, Usuarios y Roles (Fase 2)

### Primer arranque (obligatorio)

```bash
cd backend

# 1. Roles y permisos iniciales (idempotente)
python -m app.cli seed-rbac

# 2. Primer administrador (interactivo; pide contraseña oculta)
python -m app.cli create-admin
```

`create-admin` valida los datos con los mismos schemas Pydantic del API,
pide la contraseña con `getpass` y solo almacena el hash bcrypt.
Si ya existen administradores pide confirmación antes de crear otro.

### Flujo JWT

1. `POST /api/auth/login` con form-urlencoded (`username`, `password`) → `{"access_token": "...", "token_type": "bearer"}`.
2. El token JWT contiene solo `sub` (id usuario) y `exp`.
3. Peticiones protegidas envían `Authorization: Bearer <token>`.
4. La autorización se resuelve SIEMPRE en backend consultando roles/permisos en DB.

### Roles

| Rol (interno) | Nombre visible | Alcance |
|---------------|----------------|---------|
| `ADMIN` | Administrador | Acceso total |
| `CASHIER` | Cajero | Ventas, clientes (lectura/creación/actualización), caja |
| `INVENTORY_MANAGER` | Encargado de inventario | Productos, inventario, proveedores, reportes |

La lógica usa únicamente el nombre interno (`Role.name`), nunca el visible.

### Permisos

Catálogo centralizado en `app/core/rbac.py`
(`ALL_PERMISSIONS`, `ROLE_PERMISSIONS`). Formato `dominio.accion`.
Para proteger un endpoint nuevo:

```python
from app.core.dependencies import require_permission

@router.post("/products")
def create_product(
    _: Annotated[User, Depends(require_permission("products.create"))],
    db: Annotated[Session, Depends(get_db)],
): ...
```

Cambiar permisos de un rol = editar `ROLE_PERMISSIONS` + re-ejecutar
`seed-rbac`; no requiere tocar endpoints.

### Reglas de seguridad implementadas

- Hash bcrypt (12 rondas) vía librería `bcrypt` directa (sin passlib).
- Errores de login genéricos (evita enumeración de usuarios).
- `DELETE /api/users/{id}` = desactivación lógica; un admin no puede autodesactivarse.
- `UserResponse` jamás incluye `password_hash`.
- Tokens expirados/inválidos → 401; sin permiso → 403 `PERMISSION_DENIED`.

## Ejecución

### Backend

```bash
cd backend
uvicorn app.main:app --reload
```

El backend estará disponible en: http://localhost:8000

Documentación API: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend
npm run dev
```

El frontend estará disponible en: http://localhost:5173

## Endpoints Disponibles

| Método | Ruta | Descripción | Permisos |
|--------|------|-------------|----------|
| GET | `/api/health` | Estado del sistema | público |
| GET | `/api/info` | Información de la aplicación | público |
| POST | `/api/auth/login` | Login OAuth2 → JWT | público |
| GET | `/api/auth/me` | Usuario autenticado actual | JWT válido |
| GET/POST | `/api/users` | Listar / crear usuarios | `users.read` / `users.create` |
| GET/PATCH/DELETE | `/api/users/{id}` | Ver / actualizar / desactivar usuario | `users.*` |
| GET/POST | `/api/categories` | Listar / crear categorías | `categories.read` / `categories.create` |
| GET/PATCH/DELETE | `/api/categories/{id}` | Ver / actualizar / desactivar categoría | `categories.*` |
| GET | `/api/products?q=&category_id=&supplier_id=&is_active=&low_stock=` | Listar productos (filtros + `{items,total}`) | `products.read` |
| GET | `/api/products/barcode/{barcode}` | Consulta por código de barras (activos) | `products.read` |
| POST/PATCH/DELETE | `/api/products[/{id}]` | Crear / actualizar / desactivar producto | `products.*` |
| GET | `/api/suppliers?q=&is_active=&order_by=&order=` | Listar proveedores (`{items,total}` con `products_count`) | `suppliers.read` |
| GET | `/api/suppliers/{id}` | Detalle de proveedor (+ cantidad de productos) | `suppliers.read` |
| GET | `/api/suppliers/{id}/products?q=&is_active=` | Productos del proveedor (paginado) | `suppliers.read` |
| POST/PATCH/DELETE | `/api/suppliers[/{id}]` | Crear / actualizar / desactivar proveedor | `suppliers.*` |
| GET | `/api/inventory/movements?product_id=&movement_type=&created_by=&date_from=&date_to=` | Historial de movimientos | `inventory.read` |
| GET | `/api/inventory/low-stock` | Productos activos con stock ≤ mínimo | `inventory.read` |
| POST | `/api/inventory/entries` · `/exits` · `/returns` | Entradas, salidas y devoluciones | `inventory.create` |
| POST | `/api/inventory/adjustments` | Ajuste a stock objetivo (motivo obligatorio) | `inventory.update` |
| GET | `/api/purchases?supplier_id=&status=&date_from=&date_to=&q=` | Listar compras (`{items,total}`) | `purchases.read` |
| GET | `/api/purchases/{id}` | Detalle de compra con ítems (snapshot) | `purchases.read` |
| POST | `/api/purchases` | Crear compra DRAFT (ítems opcionales) | `purchases.create` |
| PATCH/DELETE | `/api/purchases/{id}` | Editar encabezado (DRAFT) / cancelar (lógico) | `purchases.update` / `purchases.cancel` |
| POST | `/api/purchases/{id}/confirm` | Confirmar: entrada de inventario transaccional e idempotente | `purchases.confirm` |
| POST/PATCH/DELETE | `/api/purchases/{id}/items[/{item_id}]` | Gestionar ítems (solo DRAFT) | `purchases.update` |
| GET | `/api/sales?customer_id=&status=&date_from=&date_to=&q=` | Listar ventas (`{items,total}`) | `sales.read` |
| GET | `/api/sales/{id}` | Detalle de venta con ítems (snapshot) | `sales.read` |
| POST | `/api/sales` | Crear venta DRAFT (ítems opcionales) | `sales.create` |
| PATCH/DELETE | `/api/sales/{id}` | Editar encabezado/cliente/pago (DRAFT) / cancelar (lógico) | `sales.update` / `sales.cancel` |
| POST | `/api/sales/{id}/confirm` | Confirmar: salida de stock transaccional; crédito genera cuenta por cobrar | `sales.confirm` |
| POST/PATCH/DELETE | `/api/sales/{id}/items[/{item_id}]` | Gestionar ítems del carrito (solo DRAFT) | `sales.update` |
| GET | `/api/cash/registers/current` | Caja abierta del usuario actual (`null` si ninguna) | `cash.read` |
| POST | `/api/cash/registers/open` | Abrir turno con monto inicial (único abierto por usuario) | `cash.open` |
| GET | `/api/cash/registers?user_id=&status=&date_from=&date_to=` | Historial de cajas (`{items,total}`) | `cash.read` |
| GET | `/api/cash/registers/{id}` | Detalle de caja + resumen embebido | `cash.read` |
| POST | `/api/cash/registers/{id}/close` | Cerrar caja: fija esperado/contado/diferencia | `cash.close` |
| GET | `/api/cash/registers/{id}/movements?movement_type=` | Movimientos del turno (paginado) | `cash.read` |
| GET | `/api/cash/registers/{id}/summary` | Resumen detallado del turno | `cash.report` (solo ADMIN) |
| POST | `/api/cash/movements` | Ingreso/egreso manual (`CASH_IN`/`CASH_OUT`, motivo ≥3) | `cash.movements` |

## Compras y Abastecimiento (Fase 5)

### Reglas de negocio implementadas

- **Estados:** `DRAFT` (editable) → `CONFIRMED` (inmutable, generó inventario)
  o `CANCELLED` (terminal, no confirmable). DELETE = cancelación lógica;
  nunca borrado físico.
- **Número de compra:** generado por backend (`COMP-YYYY-NNNNNN`, secuencia
  anual). En PostgreSQL usa advisory lock para evitar colisiones concurrentes.
- **Confirmación:** una única transacción — valida compra/proveedor/productos,
  registra entradas vía `InventoryService.apply_entry` (ENTRY con
  `reference_type='PURCHASE'` y `reference_id=purchase.id`) y marca CONFIRMED.
  Cualquier fallo → ROLLBACK total (compra sigue DRAFT, stock intacto, sin
  movimientos parciales).
- **Idempotencia:** confirmar dos veces devuelve 409 y no duplica stock ni
  movimientos; la fila se bloquea con `SELECT ... FOR UPDATE` para que dos
  usuarios no puedan confirmar simultáneamente.
- **Dinero:** `Decimal` + `NUMERIC(14,2)` (encabezado) / `NUMERIC(12,2)`
  (ítems), redondeo ROUND_HALF_UP; descuento > subtotal → 422.
- **Snapshot:** los ítems conservan cantidad/costos históricos aunque el
  producto cambie de precio después.
- **Precios:** confirmar NO toca `Product.sale_price` ni `Product.purchase_price`.
- **Proveedor/producto:** deben existir y estar activos al crear Y confirmar.

### Frontend

- Rutas `/purchases` (listado con filtros estado/proveedor/fechas) y
  `/purchases/:id` (detalle editable en DRAFT; solo lectura en otros estados).
- El botón Confirmar muestra un diálogo explicativo antes de aplicar el cambio;
  al terminar se recarga el detalle (stock visible en Inventario).

Después de actualizar desde una versión anterior ejecutar
`python -m app.cli seed-rbac` para crear los permisos nuevos
`purchases.read/create/update/confirm/cancel` y asignarlos a los roles
(seed idempotente).

## Clientes y Cuentas por Cobrar (Fase 6)

### Reglas de negocio implementadas

- **Clientes:** identificación opcional pero única (vacía → NULL; duplicada →
  409). DELETE = desactivación lógica; el historial financiero nunca se borra.
- **Crédito:** `credit_enabled` + `credit_limit >= 0`; el saldo
  (`current_balance`) jamás puede exceder el límite (CHECK en BD y validación
  en servicio). El límite no puede bajarse por debajo del saldo (409) ni
  habilitarse crédito sin límite > 0 (422).
- **Cuentas por cobrar:** `OPEN → PARTIALLY_PAID → PAID`, o `CANCELLED`.
  Invariantes CHECK: `original_amount > 0`, `balance = original_amount -
  paid_amount >= 0`. Crear una cuenta suma al saldo del cliente; exige crédito
  habilitado, cupo suficiente y cliente activo (409 con código específico).
- **Pagos atómicos:** una transacción bloquea la cuenta y el cliente
  (`SELECT ... FOR UPDATE`), valida monto ≤ saldo, inserta el pago, actualiza
  cuenta y descuenta el saldo vía `CustomerCreditService` (ÚNICO punto de
  cambio de saldo). Fallo a mitad → ROLLBACK completo.
- **Idempotencia:** `idempotency_key` única opcional; repetir la clave devuelve
  el pago original (200) sin mover saldos. Sin clave, cada pago es nuevo.
- **Anulación:** solo cuentas OPEN/PARTIALLY_PAID; el saldo restante sale del
  cliente (write-off) y los abonos previos se conservan como historial.
- **Estado de cuenta:** `GET /api/customers/{id}/statement` resume crédito,
  conteos por estado, deuda vigente (`total_balance`) y listados paginados.
- **Dinero:** `Decimal`/`NUMERIC(14,2)`; serializado como string al frontend.

### Frontend

- Rutas `/clientes` (listado con búsqueda/filtros estado/crédito, formulario
  con sección de crédito) y `/clientes/:id` (tarjetas de crédito/deuda,
  tabla de cuentas con Abonar/Anular según permiso, historial de pagos).
- El modal de abono genera automáticamente una `idempotency_key` estable por
  intento: reintentar tras un error de red nunca cobra dos veces.

Después de actualizar desde una versión anterior ejecutar
`python -m app.cli seed-rbac` para crear los permisos nuevos
`customers.delete` y `receivables.read/create/payment/cancel` y asignarlos a
los roles (seed idempotente).

## Ventas y Facturación (Fase 7)

### Reglas de negocio implementadas

- **Ciclo de vida:** `DRAFT → CONFIRMED | CANCELLED`. Solo DRAFT es editable,
  recibe ítems o se cancela; CONFIRMED es inmutable (re-confirmar → 409) e
  igual que compras nunca se borra físicamente.
- **Numeración:** `VTA-YYYY-NNNNNN` con lock de numeración + reintento ante
  colisión (mismo patrón que compras).
- **Snapshot de precios:** cada ítem guarda su `unit_price` al momento; cambiar
  el precio del producto no altera ventas pasadas.
- **Confirmación atómica:** un solo commit bloquea la venta, valida productos,
  descuenta stock vía `InventoryService` (movimientos EXIT trazables con
  `reference_type='SALE'`) y, si es a crédito, crea la cuenta por cobrar vía
  `CustomerCreditService`. Cualquier fallo (stock insuficiente, cupo excedido)
  hace ROLLBACK completo: ni stock ni saldo quedan tocados.
- **Pagos:** CASH asume pago exacto si no se registra efectivo; con monto
  exige cubrir el total (422) y calcula vuelto. CARD/TRANSFER registran pago
  completo. CREDIT exige cliente activo con crédito habilitado y cupo
  suficiente; el cobro real ocurre al abonar la cuenta generada.
- **Dinero:** `Decimal`/NUMERIC; subtotal/descuento/impuesto por ítem y
  encabezado, ROUND_HALF_UP.

### Frontend

- Rutas `/ventas` (historial con filtros estado/número/fechas),
  `/pos` (búsqueda por nombre o código de barras, carrito con control de
  disponibilidad, cliente opcional con crédito visible, métodos de pago,
  vuelto estimado; cobrar = crear + confirmar en un paso) y `/ventas/:id`
  (comprobante con Confirmar/Cancelar según estado y permisos).

Después de actualizar desde una versión anterior ejecutar
`python -m app.cli seed-rbac` para crear los permisos nuevos
`sales.update/confirm/cancel` y asignarlos a los roles (seed idempotente).

## Caja y Control de Efectivo (Fase 8)

### Reglas de negocio implementadas

- **Ciclo del turno:** `OPEN → CLOSED` (o `CANCELLED`, reservado). Un cajero
  tiene a lo sumo UNA caja abierta (índice parcial único
  `user_id WHERE status='OPEN'`; doble apertura → 409
  `REGISTER_ALREADY_OPEN`). Tras cerrar puede abrirse un turno nuevo.
- **Apertura:** crea la caja y su movimiento `OPENING` en la MISMA
  transacción; nunca existe caja abierta sin OPENING. Monto ≥ 0 (422).
- **Cierre:** bloquea la fila (`SELECT ... FOR UPDATE`), calcula el efectivo
  esperado desde los movimientos, guarda esperado/contado/diferencia,
  `closed_at`, `closed_by_id` y pasa a CLOSED en un solo commit. Doble
  cierre → 409. La diferencia puede ser negativa (faltante) o positiva
  (sobrante); una caja cerrada queda con montos congelados.
- **Movimientos:** `OPENING | SALE | RECEIVABLE_PAYMENT | CASH_IN |
  CASH_OUT | ADJUSTMENT` (ADJUSTMENT reservado, no expuesto por API).
  Append-only: nunca se editan ni eliminan.
- **Regla de efectivo (`cash_delta`, única fuente de verdad):**
  OPENING/CASH_IN suman, CASH_OUT resta; SALE y RECEIVABLE_PAYMENT suman
  SOLO con medio CASH; CARD/TRANSFER se registran para trazabilidad pero
  NO mueven el efectivo físico; venta CREDIT no genera movimiento (la
  deuda vive en la cuenta por cobrar).
- **Integración automática:** confirmar una venta o registrar un abono
  crea el movimiento de caja dentro de la MISMA transacción del servicio
  origen (sin commits propios). Sin caja abierta es no-op: la venta/pago
  sigue siendo válido fuera de un turno.
- **Idempotencia estructural:** índice único parcial
  `(reference_type, reference_id)`: repetir la confirmación de una venta o
  el replay de un pago jamás duplica movimientos.
- **Ingresos/egresos manuales:** solo `CASH_IN`/`CASH_OUT`, monto > 0,
  motivo obligatorio (≥3); CASH_OUT rechazado con 409 si deja el efectivo
  en negativo.
- **Dinero:** `Decimal`/`NUMERIC(14,2)`; JSON como string.

### Frontend

- Ruta `/caja` (visible para ADMIN/CASHIER): dashboard del turno (monto
  inicial, ventas en efectivo, abonos recibidos, ingresos/egresos,
  tarjeta/transferencia como "no efectivo", esperado destacado), tabla
  paginada de movimientos e historial de turnos cerrados con su
  diferencia.
- Acciones: Abrir caja (monto inicial + notas), Registrar ingreso/egreso
  (modal con motivo), Cerrar caja (muestra esperado, pide contado y
  previsualiza la diferencia con advertencias claras de faltante/sobrante).

Después de actualizar desde una versión anterior ejecutar
`python -m app.cli seed-rbac` para crear el permiso nuevo `cash.report`
y asignarlo a ADMIN (seed idempotente). Migración: `0007_cash`.

## Reportes y Exportación (Fase 9)

### Reglas de negocio implementadas

- **9 reportes** en JSON (vista previa) y PDF/Excel: ventas, productos
  vendidos, inventario valorizado, stock bajo, compras, caja, clientes con
  crédito, cuentas por cobrar y utilidades.
- **Endpoints:** `GET /api/reports/{tipo}` (`reports.read`) y
  `GET /api/reports/{tipo}/export?format=pdf|excel` (`reports.export`);
  permisos ya existentes en el seed (ADMIN + INVENTORY_MANAGER; CASHIER →
  403). No requiere migración ni `seed-rbac` adicional.
- **Totales globales:** calculados en SQL sobre TODAS las filas del filtro;
  `skip`/`limit` solo recortan la página JSON. La exportación ignora la
  paginación e incluye todo.
- **Solo lectura:** el repositorio de reportes nunca muta estado; las
  consultas usan agregados (`SUM`/`CASE`/`GROUP BY`) y joins puntuales.
- **Utilidades aproximadas:** costo = cantidad vendida × precio de compra
  ACTUAL del producto (los ítems no guardan snapshot del costo); nota
  explicativa incluida en los documentos. Agrupación DAY/MONTH (default
  MONTH) sobre la fecha efectiva de venta.
- **Validación por reporte:** cada tipo declara sus filtros válidos; usar un
  filtro ajeno → 422 `INVALID_FILTER_FOR_REPORT`; valor inválido de enum →
  422 `INVALID_FILTER_VALUE`; rango invertido → 422 `INVALID_DATE_RANGE`;
  formato desconocido → 422 `INVALID_EXPORT_FORMAT`; tipo inexistente →
  404 `REPORT_NOT_FOUND`.
- **Archivos:** PDF vía `reportlab`, Excel vía `openpyxl`; descarga como
  binario con `Content-Disposition: attachment;
  filename="reporte-{tipo}-{AAAAMMDD}-{HHMM}.{pdf|xlsx}"`.

### Frontend

- Ruta `/reportes` (nav visible solo para ADMIN/INVENTORY_MANAGER):
  selector de tipo, filtros dinámicos según el reporte (vendedor/cajero solo
  para ADMIN), tabla genérica generada desde `columns`, fila TOTALES,
  paginación y botones "Exportar PDF / Excel" que descargan el blob
  respetando el filename del header.

## Productos e Inventario (Fase 3)

### Reglas de negocio implementadas

- **Stock:** cada movimiento (entrada/salida/devolución/ajuste) actualiza el stock
  del producto en la misma transacción, con bloqueo de fila
  (`SELECT ... FOR UPDATE`) y registro de `previous_stock`/`new_stock`.
- **Salidas:** rechazadas con 409 `INSUFFICIENT_STOCK` si no hay disponibilidad.
- **Ajustes:** reciben `new_stock` absoluto; el servicio calcula el delta y
  rechaza ajustes sin cambio real. Motivo obligatorio.
- **Inmutabilidad:** los movimientos no se editan ni eliminan (no hay endpoints).
- **Borrado lógico:** productos/categorías se desactivan (`is_active=False`);
  una categoría con productos activos no puede desactivarse (409).
- **Barcode:** único pero opcional; vacío → NULL; la búsqueda ignora inactivos.

### Dinero

Precios usan `Decimal`/`Numeric(12,2)` y llegan al frontend como **string**
(`"18.00"`). En TypeScript los campos monetarios son `string`; formatear con
`formatCurrency()` (`src/utils/format.ts`).

### Frontend

- Rutas: `/login`, `/categorias`, `/proveedores`, `/productos`, `/inventario`.
- `AuthContext` restaura la sesión desde el token en localStorage al cargar.
- La UI oculta acciones según rol: ADMIN e INVENTORY_MANAGER pueden editar;
  CASHIER ve todo en modo lectura.
- Inventario tiene pestañas: Existencias (con botones de operación),
  Movimientos (historial con filtros) y Stock bajo (alertas).

## Proveedores (Fase 4)

### Reglas de negocio implementadas

- **Borrado lógico:** `DELETE` solo desactiva (`is_active=False`); nunca hay
  borrado físico, tenga o no productos asociados.
- **Identificación:** opcional pero única; vacía → NULL. Duplicada → 409.
- **Nombre único:** duplicado → 409 `SUPPLIER_NAME_ALREADY_EXISTS`.
- **Email opcional** validado con `EmailStr` (inválido → 422).
- **Teléfono como texto:** admite prefijos, espacios, guiones, código país.
- **Relación con productos:** un producto activo no admite proveedor inexistente
  (400) ni inactivo (409); reactivar un producto cuyo proveedor quedó inactivo
  se rechaza hasta cambiar/quitar el proveedor. Los productos ya asociados
  permanecen intactos al desactivar el proveedor.
- **Listado:** búsqueda por nombre/identificación/email/teléfono (`q`), filtro
  por estado, ordenamiento seguro (`order_by` ∈ name|created_at|updated_at) y
  paginación `{items,total}`; cada ítem trae `products_count` (sin N+1).
- **Productos del proveedor:** `GET /api/suppliers/{id}/products` paginado,
  con búsqueda y filtro de estado; solo devuelve productos de ese proveedor.

Después de actualizar desde una versión anterior ejecutar
`python -m app.cli seed-rbac` para crear el permiso nuevo `suppliers.delete`
y asignarlo a los roles (seed idempotente).

## Tests

### Backend

```bash
cd backend

# Ejecutar todas las pruebas
pytest

# Ejecutar un archivo específico
pytest tests/test_health.py

# Ejecutar una función específica
pytest tests/test_health.py::test_health_check

# Con cobertura
pytest --cov=app --cov-report=html
```

### Frontend

```bash
cd frontend

# Build de producción
npm run build

# Build de desarrollo
npm run build --mode development
```

## Docker

### Levantar todo (PostgreSQL + Backend)

```bash
docker compose up -d
```

### Ver logs

```bash
docker compose logs -f backend
docker compose logs -f db
```

### Detener

```bash
docker compose down
```

### Detener y eliminar datos

```bash
docker compose down -v
```

## Estructura del Proyecto

```
sistema-facturacion-inventario-ia/
├── backend/
│   ├── app/
│   │   ├── main.py          # Punto de entrada FastAPI
│   │   ├── core/            # Config, security (JWT+bcrypt), rbac, dependencies
│   │   ├── db/              # Session, base declarativa, seed (roles/permisos)
│   │   ├── models/          # Modelos SQLAlchemy (User, Role, Permission)
│   │   ├── schemas/         # Schemas Pydantic
│   │   ├── repositories/    # Acceso a datos
│   │   ├── services/        # Lógica de negocio
│   │   ├── api/routes/      # Endpoints HTTP
│   │   ├── cli.py           # seed-rbac, create-admin
│   │   ├── auth/            # Reservado para utilidades de auth
│   │   ├── ai/              # Integración IA
│   │   └── reports/         # Generación de reportes
│   ├── tests/               # Pruebas
│   ├── alembic/             # Migraciones
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # Componentes React
│   │   ├── pages/           # Páginas
│   │   ├── services/        # Servicios API
│   │   ├── hooks/           # Custom hooks
│   │   ├── contexts/        # Contexts React
│   │   ├── types/           # Interfaces TypeScript
│   │   ├── utils/           # Utilidades
│   │   └── routes/          # Rutas
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── ARCHITECTURE.md      # Documentación de arquitectura
│   └── DEVELOPMENT.md       # Esta guía
├── docker-compose.yml
├── AGENTS.md
├── README.md
└── .gitignore
```

## Variables de Entorno

### Backend (.env)

| Variable | Descripción | Ejemplo |
|----------|------------|---------|
| `APP_NAME` | Nombre de la aplicación | Sistema de Facturación... |
| `APP_ENV` | Entorno (development/production) | development |
| `DEBUG` | Modo debug | true |
| `DATABASE_URL` | URL de PostgreSQL | postgresql://user:pass@host/db |
| `SECRET_KEY` | Clave secreta JWT | mi-clave-secreta |
| `ALGORITHM` | Algoritmo JWT | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de expiración token | 30 |
| `OPENAI_API_KEY` | Clave API OpenAI | sk-... |
| `CORS_ORIGINS` | Orígenes CORS permitidos | ["http://localhost:5173"] |

### Frontend (.env)

| Variable | Descripción | Ejemplo |
|----------|------------|---------|
| `VITE_API_URL` | URL del backend API | http://localhost:8000/api |

## Decisiones técnicas (Fase 1)

Desviaciones menores respecto a `docs/ARCHITECTURE.md`, documentadas según las reglas del proyecto:

| Tema | Arquitectura decía | Implementación actual | Motivo |
|------|--------------------|-----------------------|--------|
| Driver PostgreSQL | psycopg2 | psycopg3 (`postgresql+psycopg://`) | Driver moderno mantenido por psycopg.org, API async futura |
| React | React 18 | React 19 | Versión estable actual al crear el proyecto |
| Tailwind CSS | tailwind.config.js + postcss.config.js | Tailwind v4 vía plugin `@tailwindcss/vite` (sin configs) | Tailwind v4 elimina archivos de configuración |
| Router frontend | React Router v6 | React Router v6.30 instalado (Fase 3) | Navegación real entre módulos con rutas protegidas |
| DB en tests | PostgreSQL | SQLite (archivo temporal) para pytest | Tests rápidos sin depender de PG |

### Decisiones técnicas (Fase 3)

| Tema | Decisión | Motivo |
|------|----------|--------|
| Dinero | `Decimal` + `Numeric(12,2)`; JSON como string | Precisión exacta; evita bugs de float en JS |
| Concurrencia de stock | `SELECT ... FOR UPDATE` + CHECK `stock >= 0` | Evita condiciones de carrera; el CHECK es red de seguridad a nivel BD |
| Ajustes de inventario | `new_stock` absoluto + motivo obligatorio; delta calculado en servicio | Semántica clara de conteo físico |
| Movimientos | Inmutables (append-only) con stock previo/nuevo y usuario | Trazabilidad y auditoría confiables |
| Borrado | Lógico (`is_active=False`) para productos/categorías | Conserva integridad referencial e historial |
| Proveedores | Modelo mínimo creado, sin endpoints/UI aún | La FK de products lo requiere; CRUD completo va en Fase 4 |
| Listados | Productos/movimientos retornan `{items,total}` | Paginación precisa en frontend |

### Decisiones técnicas (Fase 4)

| Tema | Decisión | Motivo |
|------|----------|--------|
| Identificación | `String(50)` opcional con índice único (NULL múltiples permitidos) | Sin formato de país impuesto; la unicidad solo aplica cuando existe |
| Nombre | Se mantiene `UNIQUE` heredado de `0002_catalog` | Consistencia con categorías; evitar migración destructiva innecesaria |
| Email | Pydantic `EmailStr` (`email-validator`, ya en requirements) | Validación robusta sin dependencias nuevas |
| Teléfono | Texto libre `String(50)`, nunca numérico | Admite prefijos/espacios/guiones/código país |
| Borrado | Solo lógico, incluso con productos asociados | Preserva integridad referencial e historial; FK RESTRICT como red |
| products_count | LEFT JOIN agregado en una consulta | Evita N+1 en el listado |
| Ordenamiento | Whitelist `order_by`/`order` en repositorio | Sin SQL dinámico inseguro; inválido → 422 |
| Ruta frontend | `/proveedores` (spec sugería `/suppliers`) | Consistencia con rutas existentes en español |
| Selector proveedor | Carga activos (limit 100) + filtro client-side | No carga todos los proveedores innecesariamente |

### Decisiones técnicas (Fase 5)

| Tema | Decisión | Motivo |
|------|----------|--------|
| Cambio de stock | Solo vía `InventoryService.apply_entry` (sin commit) dentro de la transacción de confirmación | Único punto de mutación de stock; atomicidad garantizada |
| Idempotencia | Segunda confirmación → 409 `PURCHASE_ALREADY_CONFIRMED` | Explícito y auditable; imposible duplicar entradas |
| Concurrencia | `SELECT ... FOR UPDATE` sobre la compra + advisory lock para el número | Dos confirmaciones simultáneas no generan movimientos dobles |
| Número de compra | `COMP-YYYY-NNNNNN`, secuencia por año, UNIQUE en BD + reintento | Legible, generado por backend, sin colisiones |
| Dinero | `Decimal`/`NUMERIC(14,2)`; JSON string; ROUND_HALF_UP a escala 2 | Sin errores de float ni redondeo inconsistente |
| Snapshot histórico | Ítems copian cantidad/costos al crear/editar; nunca se recalculan | Las compras pasadas reflejan lo pagado realmente |
| Precios comerciales | Confirmar no modifica `Product.purchase_price`/`sale_price` | Evita alterar precios silenciosamente; costo histórico vive en el ítem |
| DELETE | Cancelación lógica (`CANCELLED`) | Trazabilidad contable; nada se borra físicamente |
| Movimientos | Nuevo campo `reference_type` (`'PURCHASE'`) + `reference_id` | Auditoría Compra → Movimiento → Stock |
| Ruta frontend | `/purchases` (spec la pide así) | Igual que la spec; resto del proyecto usa español |
| RBAC | CASHIER solo `purchases.read`; INVENTORY_MANAGER ciclo completo | El cajero consulta pero no gestiona abastecimiento |

### Decisiones técnicas (Fase 8)

| Tema | Decisión | Motivo |
|------|----------|--------|
| Un turno por cajero | Índice parcial único `user_id WHERE status='OPEN'` + re-chequeo tras IntegrityError | La BD es red de seguridad ante carreras; el servicio da un error claro (409) |
| Regla de efectivo | Función única `cash_delta(type, method)` en `models/cash.py` | Una sola fuente de verdad para esperado; imposible divergencias entre cierre y resumen |
| Medios electrónicos | CARD/TRANSFER registran movimiento sin tocar efectivo físico | Trazabilidad completa sin inflar el cajón; el esperado solo cuenta CASH |
| Integración ventas/abonos | Hooks sin commit (`record_*_in_transaction`) invocados antes del COMMIT del servicio origen | Atomicidad: venta y movimiento nacen y mueren juntos; rollback total si algo falla |
| Idempotencia | Índice único parcial `(reference_type, reference_id)` + chequeo previo | Reprocesos/reintentos nunca duplican efectivo; la BD respalda al servicio |
| Venta CREDIT | No genera movimiento de caja | El cobro real se registra cuando el cliente abona (RECEIVABLE_PAYMENT) |
| Vuelto de ventas CASH | En caja entra el TOTAL de la venta; el vuelto sale del cajón | El efectivo esperado refleja el flujo físico real del turno |
| Cierre | FOR UPDATE + cálculo desde movimientos + fijación de montos en un commit | Doble cierre imposible; caja cerrada queda como comprobante inmutable |
| Egresos | Rechazo 409 si dejan efectivo negativo | El cajón no puede quedar en negativo por operación manual |
| ADJUSTMENT | Reservado en modelo/CHECK, no expuesto por API | Preparado para ajustes futuros de cierre sin migración nueva |
| RBAC | Nuevo `cash.report` solo ADMIN; summary no embebido para CASHIER | Separación consulta-operación; el cajero ve su resumen vía detalle/current |

## Convenciones

### Python

- Type hints en todas las funciones.
- Docstrings en clases y funciones públicas.
- Formato con black (futuro).
- Linting con ruff (futuro).

### TypeScript

- TypeScript estricto.
- Interfaces para props y estados.
- Componentes funcionales con hooks.

### Git

- Commits descriptivos en inglés o español.
- Branches por feature.
- PR reviews antes de merge.
