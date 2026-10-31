import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Configurar variables de entorno necesarias para las pruebas
os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/taller_mecanico_test",
)

from main import app
from app.core.configuracion import configuracion
from app.core.database import get_session
from app.core.seguridad import crear_token_acceso, hash_password_sync
from app.modules.usuarios.models import AsignacionRol, Usuario


@pytest_asyncio.fixture
async def cliente():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# Alias para compatibilidad
client = cliente


# ---------------------------------------------------------------------------
# Helpers compartidos de las suites de administración (C-12, task 2.6)
# ---------------------------------------------------------------------------


def token_de_sesion(usuario_id: int, roles: list[str] | None = None) -> str:
    """Emite un JWT de prueba sin pasar por `POST /auth/login`."""
    return crear_token_acceso(
        usuario_id=usuario_id,
        roles=roles or [],
        iat=datetime.now(timezone.utc),
    )


def cliente_http(token: str | None = None) -> AsyncClient:
    """Cliente ASGI contra la app real, con cookie `access_token` opcional."""
    http = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token is not None:
        http.cookies.set("access_token", token)
    return http


async def crear_usuario_prueba(
    sesion: AsyncSession,
    email: str,
    *,
    nombre: str = "Usuario de prueba",
    password: str = "Password123",
    activo: bool = True,
    debe_cambiar_password: bool = False,
    password_cambiada_en: datetime | None = None,
) -> Usuario:
    """Crea y hace `flush()` de un usuario de prueba."""
    usuario = Usuario(
        email=email,
        nombre=nombre,
        password_hash=hash_password_sync(password),
        activo=activo,
        debe_cambiar_password=debe_cambiar_password,
        password_cambiada_en=password_cambiada_en,
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


async def crear_asignacion_prueba(
    sesion: AsyncSession,
    usuario_id: int,
    rol: str,
    *,
    desde: datetime | None = None,
    vence_en: datetime | None = None,
    revocada_en: datetime | None = None,
    otorgada_por: int | None = None,
) -> AsignacionRol:
    """Crea y hace `flush()` de una asignación de rol de prueba."""
    asignacion = AsignacionRol(
        usuario_id=usuario_id,
        rol=rol,
        desde=desde or datetime.now(timezone.utc),
        vence_en=vence_en,
        revocada_en=revocada_en,
        otorgada_por=otorgada_por,
    )
    sesion.add(asignacion)
    await sesion.flush()
    return asignacion


async def crear_admin_prueba(
    sesion: AsyncSession,
    email: str = "admin@taller.test",
    *,
    nombre: str = "Administrador",
) -> tuple[Usuario, str]:
    """Crea un usuario con `ADMIN` vigente y devuelve `(usuario, token)`."""
    admin = await crear_usuario_prueba(sesion, email, nombre=nombre)
    await crear_asignacion_prueba(sesion, admin.id, "ADMIN", otorgada_por=admin.id)
    return admin, token_de_sesion(admin.id, ["ADMIN"])


@pytest.fixture
def montar_sonda():
    """Monta un router sonda sobre la app real y lo retira al terminar."""
    agregadas = []

    def _montar(router):
        antes = {id(ruta) for ruta in app.router.routes}
        app.include_router(router)
        agregadas.extend(ruta for ruta in app.router.routes if id(ruta) not in antes)
        return router

    yield _montar

    for ruta in agregadas:
        if ruta in app.router.routes:
            app.router.routes.remove(ruta)


def sonda_roles(*roles: str, ruta: str):
    """Sonda mínima que exige al menos uno de `roles` y devuelve el `usuario_id`."""
    from fastapi import APIRouter, Depends

    from app.core.dependencies import SesionActual, require_roles

    sonda = APIRouter()

    @sonda.get(ruta)
    async def endpoint(
        sesion_actual: SesionActual = Depends(require_roles(*roles)),
    ) -> dict[str, int]:
        return {"usuario_id": sesion_actual.usuario.id}

    return sonda




@pytest_asyncio.fixture
async def test_db_session():
    """
    Fixture para pruebas que requieren conexión a PostgreSQL real.
    Abre una conexión, inicia una transacción y aplica rollback al finalizar cada test
    para garantizar el aislamiento y la limpieza del estado.
    Sobrescribe automáticamente la dependencia get_session de FastAPI.
    """
    test_db_url = os.getenv("TEST_DATABASE_URL", str(configuracion.database_url))
    engine = create_async_engine(test_db_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            trans = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with session_factory() as session:
                async def override_get_session():
                    yield session

                app.dependency_overrides[get_session] = override_get_session
                try:
                    yield session
                finally:
                    app.dependency_overrides.pop(get_session, None)
                    await trans.rollback()
    except Exception as exc:
        pytest.skip(f"Base de datos PostgreSQL no disponible o no accesible: {exc}")
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seed_session_factory():
    """
    Fábrica de sesiones para probar `seed.py` contra PostgreSQL real.

    Mantiene una transacción externa con rollback al final del test. El seed
    abre su propia sesión y su `session.begin()` se traduce en un SAVEPOINT,
    de modo que la doble ejecución es verificable y la base queda intacta.
    """
    test_db_url = os.getenv("TEST_DATABASE_URL", str(configuracion.database_url))
    engine = create_async_engine(test_db_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            trans = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session_factory
            finally:
                await trans.rollback()
    except Exception as exc:
        pytest.skip(f"Base de datos PostgreSQL no disponible o no accesible: {exc}")
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def contexto_auth():
    """
    Fixture para probar módulos de autenticación y auditoría independiente contra PostgreSQL real.
    Sobrescribe get_session, obtener_sesion_auditoria y obtener_sesion_cambio_password
    con sesiones ligadas a la misma conexión externa bajo create_savepoint para permitir
    commit() y rollback aislado.
    """
    test_db_url = os.getenv("TEST_DATABASE_URL", str(configuracion.database_url))
    engine = create_async_engine(test_db_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            trans = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async def override_get_session():
                async with session_factory() as session:
                    yield session
                    await session.commit()

            async def override_obtener_sesion_auditoria():
                async with session_factory() as session:
                    yield session
                    await session.commit()

            async def override_obtener_sesion_cambio_password():
                async with session_factory() as session:
                    yield session
                    await session.commit()

            async def override_obtener_sesion_admin_usuarios():
                async with session_factory() as session:
                    yield session
                    await session.commit()

            try:
                from app.modules.usuarios.repository import (
                    obtener_sesion_admin_usuarios,
                    obtener_sesion_auditoria,
                    obtener_sesion_cambio_password,
                )
                app.dependency_overrides[obtener_sesion_auditoria] = override_obtener_sesion_auditoria
                app.dependency_overrides[obtener_sesion_cambio_password] = (
                    override_obtener_sesion_cambio_password
                )
                app.dependency_overrides[obtener_sesion_admin_usuarios] = (
                    override_obtener_sesion_admin_usuarios
                )
            except ImportError:
                pass

            app.dependency_overrides[get_session] = override_get_session

            try:
                async with session_factory() as test_session:
                    yield test_session
            finally:
                app.dependency_overrides.pop(get_session, None)
                try:
                    from app.modules.usuarios.repository import (
                        obtener_sesion_admin_usuarios,
                        obtener_sesion_auditoria,
                        obtener_sesion_cambio_password,
                    )
                    app.dependency_overrides.pop(obtener_sesion_auditoria, None)
                    app.dependency_overrides.pop(obtener_sesion_cambio_password, None)
                    app.dependency_overrides.pop(obtener_sesion_admin_usuarios, None)
                except ImportError:
                    pass
                await trans.rollback()
    except Exception as exc:
        pytest.skip(f"Base de datos PostgreSQL no disponible o no accesible: {exc}")
    finally:
        await engine.dispose()
