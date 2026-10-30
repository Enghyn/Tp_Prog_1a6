import os
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import BaseModel, ConfigDict, EmailStr

os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

from main import app


class EsquemaPrueba(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    correo: EmailStr


@app.post("/prueba/validar")
async def prueba_validar(datos: EsquemaPrueba):
    return datos


@pytest.mark.asyncio
async def test_campo_extra_devuelve_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        respuesta = await ac.post("/prueba/validar", json={"nombre": "test", "correo": "test@test.com", "extra": "malo"})
        assert respuesta.status_code == 422


@pytest.mark.asyncio
async def test_formato_error_uniforme():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        respuesta = await ac.post("/prueba/validar", json={"nombre": "test"})
        assert respuesta.status_code == 422
        datos = respuesta.json()
        assert "detail" in datos
        assert "codigo" in datos
