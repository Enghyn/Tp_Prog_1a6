import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Configurar variables de entorno necesarias para las pruebas
os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

from main import app
from app.core.configuracion import configuracion
from app.core.database import get_session


@pytest_asyncio.fixture
async def cliente():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# Alias para compatibilidad
client = cliente


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
