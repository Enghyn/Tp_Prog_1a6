import logging
import asyncio

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.exc import IntegrityError

from app.modules.health import router as health_router
from app.modules.usuarios import router as usuarios_router
from app.core.errors import ErrorAplicacion, DemasiadasPeticionesError
from app.core.seguridad import generar_hash_ficticio
from app.core.configuracion import configuracion
from app.core.database import crear_motor_bd, crear_fabricante_sesion


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar semáforo para bcrypt
    app.state.bcrypt_semaforo = asyncio.Semaphore(configuracion.bcrypt_max_concurrency)
    # Generar hash ficticio para protección contra enumeración
    app.state.hash_ficticio = generar_hash_ficticio()
    # Inicializar motor y session maker de base de datos
    app.state.engine = crear_motor_bd()
    app.state.session_maker = crear_fabricante_sesion(app.state.engine)
    yield
    # Liberar recursos del motor de base de datos
    await app.state.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="API Taller Mecánico",
        description="API para la gestión de un taller mecánico",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ErrorAplicacion)
    async def manejador_error_aplicacion(request: Request, exc: ErrorAplicacion):
        headers = {}
        if isinstance(exc, DemasiadasPeticionesError) and exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "codigo": exc.codigo},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def manejador_error_validacion(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "codigo": "ERROR_VALIDACION"},
        )

    @app.exception_handler(IntegrityError)
    async def manejador_error_integridad(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=409,
            content={"detail": "Conflicto en la operación", "codigo": "CONFLICTO_INTEGRIDAD"},
        )

    app.include_router(health_router.router)
    app.include_router(usuarios_router.router)

    return app


app = create_app()
