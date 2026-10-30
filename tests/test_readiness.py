import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import OperationalError

from main import app
from app.core.database import get_session


@pytest.mark.asyncio
async def test_health_ready_retorna_200_cuando_bd_esta_disponible():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            respuesta = await ac.get("/health/ready")
            assert respuesta.status_code == 200
            assert respuesta.json() == {"status": "ready"}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_ready_retorna_503_cuando_bd_falla():
    mock_session = AsyncMock()
    mock_session.execute.side_effect = OperationalError("connection refused", {}, None)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            respuesta = await ac.get("/health/ready")
            assert respuesta.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_ready_retorna_503_por_timeout():
    import asyncio

    mock_session = AsyncMock()

    async def consulta_lenta(*args, **kwargs):
        await asyncio.sleep(5)

    mock_session.execute.side_effect = consulta_lenta

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            respuesta = await ac.get("/health/ready")
            assert respuesta.status_code == 503
    finally:
        app.dependency_overrides.clear()
