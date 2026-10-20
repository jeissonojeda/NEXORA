import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.ai import router as ai_router
from app.api.routes.ai_operational import router as ai_operational_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cash import router as cash_router
from app.api.routes.categories import router as categories_router
from app.api.routes.customers import router as customers_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.license import router as license_router
from app.api.routes.products import router as products_router
from app.api.routes.products_import import router as products_import_router
from app.api.routes.purchases import router as purchases_router
from app.api.routes.receivables import router as receivables_router
from app.api.routes.reports import router as reports_router
from app.api.routes.sale_returns import router as sale_returns_router
from app.api.routes.sales import router as sales_router
from app.api.routes.settings import router as settings_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.taxes import router as taxes_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.licensing.local.dependencies import require_license

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    yield
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exentos de licencia: salud, autenticación y el propio módulo de licencia.
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(license_router, prefix="/api")

# Routers de negocio: exigen licencia válida (desactivado fuera de producción).
_business_dependencies = [Depends(require_license)]
app.include_router(users_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(
    categories_router, prefix="/api", dependencies=_business_dependencies
)
app.include_router(
    suppliers_router, prefix="/api", dependencies=_business_dependencies
)
app.include_router(
    products_import_router,
    prefix="/api",
    dependencies=_business_dependencies,
)
app.include_router(products_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(inventory_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(purchases_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(customers_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(
    receivables_router, prefix="/api", dependencies=_business_dependencies
)
# Devoluciones ANTES que ventas: "/sales/returns/{id}" debe resolverse
# antes que "/sales/{sale_id}" (evita que "returns" se interprete como UUID).
app.include_router(
    sale_returns_router, prefix="/api", dependencies=_business_dependencies
)
app.include_router(sales_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(cash_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(reports_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(ai_router, prefix="/api", dependencies=_business_dependencies)
app.include_router(
    ai_operational_router, prefix="/api", dependencies=_business_dependencies
)
app.include_router(
    settings_router, prefix="/api", dependencies=_business_dependencies
)
app.include_router(taxes_router, prefix="/api", dependencies=_business_dependencies)


def _cors_headers_for_error(request: Request) -> dict[str, str]:
    """Encabezados CORS para respuestas de error manejadas por la aplicación.

    El manejador registrado sobre ``Exception`` (500) se ejecuta FUERA del
    middleware CORS: sin estos encabezados el navegador bloquea la lectura de
    la respuesta y el frontend solo ve un "Network Error" sin detalle. En
    producción se respeta la lista de orígenes permitidos.
    """
    origin = request.headers.get("origin") if request is not None else None
    if not origin or origin not in settings.cors_origins_list:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
        },
        headers={**(exc.headers or {}), **_cors_headers_for_error(request)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Error interno del servidor; revise los logs para más detalle"
            ),
            "error_code": "INTERNAL_ERROR",
            "status_code": 500,
        },
        headers=_cors_headers_for_error(request),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Resource not found",
            "error_code": "NOT_FOUND",
            "status_code": 404,
        },
        headers=_cors_headers_for_error(request),
    )


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "status_code": 422,
        },
        headers=_cors_headers_for_error(request),
    )
