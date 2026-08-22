# AGENTS.md

## Status

Fase actual: Fase 1 (Fundamentos) completada. Siguiente: Fase 2 (Catálogos).

## Project intent

Sistema de facturación e inventario con IA para supermercado. Monolito modular: FastAPI backend + React/Vite/TS frontend + PostgreSQL.

## Architecture

Ver `docs/ARCHITECTURE.md` para la documentación completa.

### Estructura clave

```
backend/app/
  core/         → config, security, dependencies
  db/           → session, base, seed
  models/       → SQLAlchemy entities
  schemas/      → Pydantic validation
  repositories/ → data access (CRUD base genérico)
  services/     → business logic (aquí va la magia)
  api/routes/   → HTTP endpoints (sin lógica de negocio)
  ai/           → OpenAI integration
  reports/      → PDF & Excel generation

frontend/src/
  components/   → ui/ (genéricos) + domain/ (específicos)
  pages/        → una carpeta por módulo
  services/     → Axios calls, una por dominio
  contexts/     → AuthContext
  hooks/        → custom hooks
  types/        → interfaces TypeScript
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
