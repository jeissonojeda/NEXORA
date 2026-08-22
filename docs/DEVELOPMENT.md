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
| Router frontend | React Router v6 | No instalado aún; `src/routes/` tiene constantes de rutas | Se instalará al implementar navegación entre páginas |
| DB en tests | PostgreSQL | SQLite (archivo temporal) para pytest | Tests rápidos sin depender de PG |

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
