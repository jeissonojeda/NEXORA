# Sistema de Facturación e Inventario con IA

Sistema web profesional para la gestión integral de un supermercado, con módulo de inteligencia artificial para análisis de ventas y recomendaciones de inventario.

## Estado

**Fase 1 — Fundamentos** completada. Backend y frontend configurados con estructura base.

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

**Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Axios

**IA:** OpenAI API (futuro)

**Reportes:** PDF (reportlab/weasyprint), Excel (openpyxl) (futuro)

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

## Endpoints Disponibles

| Método | Ruta | Descripción |
|--------|------|------------|
| GET | `/api/health` | Estado del sistema y conexión DB |
| GET | `/api/info` | Información de la aplicación |
| GET | `/api/docs` | Documentación Swagger (dev) |

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
