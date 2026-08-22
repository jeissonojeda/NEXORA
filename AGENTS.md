# AGENTS.md

## Status

Fase actual: Fase 2 (Autenticación, Usuarios y Roles) completada. Siguiente: Fase 3 (Catálogos).

## Project intent

Sistema de facturación e inventario con IA para supermercado. Monolito modular: FastAPI backend + React/Vite/TS frontend + PostgreSQL.

## Architecture

Ver `docs/ARCHITECTURE.md` para la documentación completa.

### Estructura clave

```
backend/app/
  core/         → config, security (JWT+bcrypt), rbac, dependencies, exceptions
  db/           → session, base, seed (roles/permisos)
  models/       → SQLAlchemy entities (User, Role, Permission)
  schemas/      → Pydantic validation
  repositories/ → data access (CRUD base genérico)
  services/     → business logic (aquí va la magia)
  api/routes/   → HTTP endpoints (sin lógica de negocio)
  cli.py        → python -m app.cli (seed-rbac, create-admin)
  ai/           → OpenAI integration
  reports/      → PDF & Excel generation

frontend/src/
  components/   → ui/ (genéricos) + domain/ (específicos)
  pages/        → una carpeta por módulo
  services/     → Axios calls, una por dominio (api.ts + auth.ts)
  contexts/     → AuthContext
  hooks/        → custom hooks
  types/        → interfaces TypeScript (+ auth.ts)
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
