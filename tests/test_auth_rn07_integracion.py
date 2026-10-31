from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.seguridad import crear_token_acceso, hash_password_sync
from app.modules.usuarios.models import Usuario
from main import app

ACTUAL = "Provisoria1"
NUEVA = "NuevaClave2"


@pytest.mark.asyncio
async def test_get_auth_yo_rechaza_token_anterior_a_password_cambiada_en_persistido(
    contexto_auth,
) -> None:
    """America/Buenos_Aires reproduce el corrimiento naive; el token anterior debe ser 401."""
    await contexto_auth.execute(text("SET TIME ZONE 'America/Buenos_Aires'"))
    ahora = datetime.now(timezone.utc)
    cambio = ahora - timedelta(minutes=5)
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
    ahora = datetime.now(timezone.utc)
    cambio = ahora - timedelta(minutes=5)
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


# ---------------------------------------------------------------------------
# Grupo 6 — Integración real del cambio de contraseña con RN-07
# ---------------------------------------------------------------------------


async def _crear_usuario_rn07(contexto_auth, email: str) -> Usuario:
    usuario = Usuario(
        email=email,
        nombre="RN07 cambio",
        password_hash=hash_password_sync(ACTUAL),
        activo=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()
    return usuario


@pytest.mark.asyncio
async def test_cambiar_password_invalida_el_token_anterior(contexto_auth) -> None:
    usuario = await _crear_usuario_rn07(contexto_auth, "rn07-cambio@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        login = await cliente.post(
            "/auth/login", json={"email": usuario.email, "password": ACTUAL}
        )
        assert login.status_code == 200

        cambio = await cliente.post(
            "/auth/cambiar-password",
            json={"password_actual": ACTUAL, "password_nueva": NUEVA},
        )
        assert cambio.status_code == 200

        # El cliente conserva la cookie vieja: su iat es anterior al cambio.
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_token_emitido_despues_del_cambio_es_valido(contexto_auth) -> None:
    usuario = await _crear_usuario_rn07(contexto_auth, "rn07-nuevo@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        assert (
            await cliente.post(
                "/auth/login", json={"email": usuario.email, "password": ACTUAL}
            )
        ).status_code == 200
        assert (
            await cliente.post(
                "/auth/cambiar-password",
                json={"password_actual": ACTUAL, "password_nueva": NUEVA},
            )
        ).status_code == 200

        relogin = await cliente.post(
            "/auth/login", json={"email": usuario.email, "password": NUEVA}
        )
        assert relogin.status_code == 200
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 200


@pytest.mark.asyncio
async def test_token_con_iat_un_microsegundo_antes_del_cambio_es_rechazado(
    contexto_auth,
) -> None:
    ahora = datetime.now(timezone.utc)
    cambio = ahora - timedelta(minutes=5) + timedelta(microseconds=500000)
    usuario = Usuario(
        email="rn07-micro-anterior@example.com",
        nombre="RN07 micro",
        password_hash="hash",
        password_cambiada_en=cambio,
    )
    contexto_auth.add(usuario)
    await contexto_auth.flush()
    token = crear_token_acceso(
        usuario_id=usuario.id,
        roles=[],
        iat=cambio - timedelta(microseconds=1),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        cliente.cookies.set("access_token", token)
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_token_con_iat_igual_al_cambio_es_aceptado(contexto_auth) -> None:
    ahora = datetime.now(timezone.utc)
    cambio = ahora - timedelta(minutes=5) + timedelta(microseconds=500000)
    usuario = Usuario(
        email="rn07-micro-igual@example.com",
        nombre="RN07 micro",
        password_hash="hash",
        password_cambiada_en=cambio,
    )
    contexto_auth.add(usuario)
    await contexto_auth.flush()
    token = crear_token_acceso(usuario_id=usuario.id, roles=[], iat=cambio)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        cliente.cookies.set("access_token", token)
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 200
