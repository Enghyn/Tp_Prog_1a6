import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Configurar variables de entorno necesarias para las pruebas
os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

from main import app


@pytest_asyncio.fixture
async def cliente():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# Alias para compatibilidad
client = cliente
