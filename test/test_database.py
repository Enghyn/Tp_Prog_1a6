import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def test_crear_motor_y_sessionmaker():
    from app.core.database import crear_motor_bd, crear_fabricante_sesion

    engine = crear_motor_bd("postgresql+asyncpg://postgres:postgres@localhost:5432/taller_test")
    assert isinstance(engine, AsyncEngine)
    assert engine.pool._pre_ping is True

    session_maker = crear_fabricante_sesion(engine)
    assert isinstance(session_maker, async_sessionmaker)
    assert session_maker.kw.get("expire_on_commit") is False


@pytest.mark.asyncio
async def test_get_session_cierra_sin_hacer_commit():
    from app.core.database import get_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("app.core.database.session_maker", mock_session_maker):
        sesiones_obtenidas = []
        async for session in get_session():
            sesiones_obtenidas.append(session)

        assert len(sesiones_obtenidas) == 1
        assert sesiones_obtenidas[0] is mock_session
        # Regla dura: get_session NUNCA debe llamar a commit
        assert mock_session.commit.call_count == 0
        # Debe haber salido del contexto correctamente (cierre garantizado)
        mock_session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_session_cierra_incluso_con_excepcion():
    from app.core.database import get_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("app.core.database.session_maker", mock_session_maker):
        gen = get_session()
        session = await gen.__anext__()
        assert session is mock_session
        # Simular finalización o cierre anticipado del generador por FastAPI ante error
        await gen.aclose()

        assert mock_session.commit.call_count == 0
        mock_session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_inicializa_y_cierra_motor():
    from main import lifespan
    from fastapi import FastAPI

    test_app = FastAPI()
    with patch("main.crear_motor_bd") as mock_crear_motor, \
         patch("main.crear_fabricante_sesion") as mock_crear_maker, \
         patch("main.generar_hash_ficticio", return_value="dummy_hash"):

        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_crear_motor.return_value = mock_engine
        mock_maker = MagicMock()
        mock_crear_maker.return_value = mock_maker

        async with lifespan(test_app):
            assert test_app.state.engine is mock_engine
            assert test_app.state.session_maker is mock_maker

        mock_engine.dispose.assert_awaited_once()


def test_alembic_configuracion_asincrona():
    from alembic.config import Config
    import os

    alembic_cfg = Config("alembic.ini")
    script_loc = alembic_cfg.get_main_option("script_location")
    assert script_loc == "migrations"
    assert os.path.exists("migrations/env.py")
    assert os.path.exists("migrations/script.py.mako")


@pytest.mark.asyncio
async def test_fixture_db_session_rollback(test_db_session):
    from sqlalchemy import text
    # Si la base est disponible, ejecuta una consulta simple
    res = await test_db_session.execute(text("SELECT 1"))
    assert res.scalar() == 1
