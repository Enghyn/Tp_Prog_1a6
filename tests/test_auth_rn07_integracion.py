from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.seguridad import crear_token_acceso
from app.modules.usuarios.models import Usuario
from main import app


@pytest.mark.asyncio
async def test_get_auth_yo_rechaza_token_anterior_a_password_cambiada_en_persistido(
    contexto_auth,
) -> None:
    """America/Buenos_Aires reproduce el corrimiento naive; el token anterior debe ser 401."""
    await contexto_auth.execute(text("SET TIME ZONE 'America/Buenos_Aires'"))
    cambio = datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc)
    usuario = Usuario(
        email="rn07-anterior@example.com",
        nombre="RN07 anterior",
        password_hash="hash",
        password_cambiada_en=cambio,
    )
    contexto_auth.add(usuario)
    await contexto_auth.flush()
    token = crear_token_acceso(
        usuario_id=usuario.id,
        roles=[],
        iat=cambio - timedelta(minutes=10),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        cliente.cookies.set("access_token", token)
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_get_auth_yo_acepta_token_posterior_a_password_cambiada_en_persistido(
    contexto_auth,
) -> None:
    """La zona no-UTC debe mantener el instante y permitir un token posterior (200)."""
    await contexto_auth.execute(text("SET TIME ZONE 'America/Buenos_Aires'"))
    cambio = datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc)
    usuario = Usuario(
        email="rn07-posterior@example.com",
        nombre="RN07 posterior",
        password_hash="hash",
        password_cambiada_en=cambio,
    )
    contexto_auth.add(usuario)
    await contexto_auth.flush()
    token = crear_token_acceso(
        usuario_id=usuario.id,
        roles=[],
        iat=cambio + timedelta(minutes=10),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        cliente.cookies.set("access_token", token)
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 200
