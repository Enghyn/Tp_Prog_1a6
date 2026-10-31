import pytest
from fastapi import Response
from app.core.configuracion import Configuracion
from app.core.seguridad import construir_cookie_sesion, construir_cookie_borrado


def test_construir_cookie_sesion_dev():
    respuesta = Response()
    config = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="dev",
        access_token_ttl_min=60,
    )
    construir_cookie_sesion(respuesta, "token.jwt.aqui", config)
    cookie_header = respuesta.headers.get("set-cookie", "")
    assert "access_token=token.jwt.aqui" in cookie_header
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()
    assert "path=/" in cookie_header.lower()
    assert "max-age=3600" in cookie_header.lower()
    assert "secure" not in cookie_header.lower()


def test_construir_cookie_sesion_produccion_y_test():
    # Producción -> Secure=True
    resp_prod = Response()
    config_prod = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="produccion",
        access_token_ttl_min=30,
    )
    construir_cookie_sesion(resp_prod, "token.prod", config_prod)
    h_prod = resp_prod.headers.get("set-cookie", "").lower()
    assert "secure" in h_prod
    assert "max-age=1800" in h_prod

    # Test -> Secure=False
    resp_test = Response()
    config_test = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="test",
        access_token_ttl_min=15,
    )
    construir_cookie_sesion(resp_test, "token.test", config_test)
    h_test = resp_test.headers.get("set-cookie", "").lower()
    assert "secure" not in h_test


def test_construir_cookie_sesion_flag_cookie_secure_override():
    # Flag explícito COOKIE_SECURE=True fuerza secure incluso en dev
    resp_override = Response()
    cfg_override = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="dev",
        cookie_secure=True,
    )
    construir_cookie_sesion(resp_override, "token.override", cfg_override)
    assert "secure" in resp_override.headers.get("set-cookie", "").lower()

    # Flag explícito COOKIE_SECURE=False desactiva secure incluso en produccion
    resp_override_false = Response()
    cfg_override_false = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="produccion",
        cookie_secure=False,
    )
    construir_cookie_sesion(resp_override_false, "token.override.false", cfg_override_false)
    assert "secure" not in resp_override_false.headers.get("set-cookie", "").lower()


def test_construir_cookie_borrado():
    resp_del = Response()
    cfg_prod = Configuracion(
        jwt_secret="clave-secreta-para-cookies-test",
        entorno="produccion",
    )
    construir_cookie_borrado(resp_del, cfg_prod)
    h = resp_del.headers.get("set-cookie", "").lower()
    assert "access_token=" in h
    assert "httponly" in h
    assert "samesite=lax" in h
    assert "path=/" in h
    assert "secure" in h
    assert "max-age=0" in h


# ==============================================================================
# Pruebas de endpoints protegidos, resolución de sesión y logout (Secciones 8, 9, 10)
# ==============================================================================
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.core.database import get_session
from app.core.seguridad import hash_password_sync, crear_token_acceso
from app.core.dependencies import token_anterior_al_cambio
from app.modules.usuarios.models import Usuario, AsignacionRol
from app.modules.usuarios.repository import obtener_sesion_auditoria


@pytest.fixture
def mock_sesiones_auth():
    mock_sesion_dominio = AsyncMock()
    mock_sesion_auditoria = AsyncMock()

    class ContextoTransaccion:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_sesion_auditoria.begin = lambda: ContextoTransaccion()

    async def override_get_session():
        yield mock_sesion_dominio

    async def override_obtener_sesion_auditoria():
        yield mock_sesion_auditoria

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[obtener_sesion_auditoria] = override_obtener_sesion_auditoria
    try:
        yield mock_sesion_dominio, mock_sesion_auditoria
    finally:
        app.dependency_overrides.clear()


def test_token_anterior_al_cambio_puro():
    ahora = datetime(2026, 10, 30, 12, 0, 0, 0, tzinfo=timezone.utc)
    # Sin cambio de contraseña -> False
    assert token_anterior_al_cambio(ahora, None) is False

    # Token antes del cambio -> True
    cambio_posterior = datetime(2026, 10, 30, 12, 0, 0, 1, tzinfo=timezone.utc)
    assert token_anterior_al_cambio(ahora, cambio_posterior) is True

    # Token emitido en el mismo instante exacto -> False
    assert token_anterior_al_cambio(ahora, ahora) is False

    # Token posterior al cambio -> False
    cambio_anterior = datetime(2026, 10, 30, 11, 59, 59, tzinfo=timezone.utc)
    assert token_anterior_al_cambio(ahora, cambio_anterior) is False


@pytest.mark.asyncio
async def test_get_auth_yo_sin_cookie_devuelve_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/auth/yo")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Credenciales inválidas", "codigo": "CREDENCIALES_INVALIDAS"}


@pytest.mark.asyncio
async def test_get_auth_yo_token_manipulado_devuelve_401(mock_sesiones_auth):
    token = crear_token_acceso(usuario_id=1, roles=["ADMIN"], iat=datetime.now(timezone.utc))
    token_falso = token[:-4] + "fake"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.cookies.set("access_token", token_falso)
        resp = await ac.get("/auth/yo")
        assert resp.status_code == 401
        assert resp.json()["codigo"] == "CREDENCIALES_INVALIDAS"


@pytest.mark.asyncio
async def test_get_auth_yo_token_expirado_devuelve_401(mock_sesiones_auth):
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    token = crear_token_acceso(usuario_id=1, roles=["ADMIN"], iat=hace_dos_horas)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.cookies.set("access_token", token)
        resp = await ac.get("/auth/yo")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_auth_yo_usuario_inactivo_devuelve_401(mock_sesiones_auth):
    ses_dom, _ = mock_sesiones_auth
    usuario_inactivo = Usuario(
        id=1,
        email="inactivo@example.com",
        nombre="Inactivo",
        password_hash=hash_password_sync("password123"),
        activo=False,
        debe_cambiar_password=False,
    )
    ses_dom.get = AsyncMock(return_value=usuario_inactivo)

    token = crear_token_acceso(usuario_id=1, roles=["ADMIN"], iat=datetime.now(timezone.utc))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.cookies.set("access_token", token)
        resp = await ac.get("/auth/yo")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_auth_yo_exitoso_y_rn04_roles_vigentes(mock_sesiones_auth):
    ses_dom, _ = mock_sesiones_auth
    ahora = datetime.now(timezone.utc)
    usuario = Usuario(
        id=5,
        email="empleado@example.com",
        nombre="Empleado",
        password_hash=hash_password_sync("password123"),
        activo=True,
        debe_cambiar_password=False,
        password_cambiada_en=None,
        asignaciones=[
            AsignacionRol(id=1, usuario_id=5, rol="RECEPCION", desde=ahora, revocada_en=None, vence_en=None),
            AsignacionRol(id=2, usuario_id=5, rol="ADMIN", desde=ahora, revocada_en=ahora, vence_en=None),  # Revocado
        ],
    )
    ses_dom.get = AsyncMock(return_value=usuario)

    # El token tiene rol "HACKER" inyectado, pero la base manda (RN-04).
    # La consulta de roles vive ahora en el repositorio (D3); se simula su
    # resultado para este test con una sesión mockeada.
    token = crear_token_acceso(usuario_id=5, roles=["HACKER"], iat=ahora)
    with patch(
        "app.modules.usuarios.router.get_roles_vigentes",
        new=AsyncMock(return_value=["RECEPCION"]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ac.cookies.set("access_token", token)
            resp = await ac.get("/auth/yo")
            assert resp.status_code == 200
            data = resp.json()
            assert data["usuario"]["id"] == 5
            assert data["usuario"]["email"] == "empleado@example.com"
            assert "password_hash" not in data["usuario"]
            # Debe contener sólo el rol vigente en base, sin "ADMIN" (revocado) y sin "HACKER" (del token)
            assert data["roles"] == ["RECEPCION"]
            assert "token" in data


@pytest.mark.asyncio
async def test_get_auth_yo_rn07_invalida_token_previo_a_cambio_password(mock_sesiones_auth):
    ses_dom, _ = mock_sesiones_auth
    ahora = datetime.now(timezone.utc)
    # Token emitido antes del cambio
    iat_token = ahora - timedelta(seconds=10)
    # Contraseña cambiada 1 microsegundo después
    cambio_pw = iat_token + timedelta(microseconds=1)

    usuario = Usuario(
        id=1,
        email="user@example.com",
        nombre="User",
        password_hash="hash",
        activo=True,
        password_cambiada_en=cambio_pw,
        asignaciones=[],
    )
    ses_dom.get = AsyncMock(return_value=usuario)

    token_viejo = crear_token_acceso(usuario_id=1, roles=[], iat=iat_token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.cookies.set("access_token", token_viejo)
        resp = await ac.get("/auth/yo")
        # Debe fallar con 401 porque iat < password_cambiada_en por 1 microsegundo
        assert resp.status_code == 401

    # Token emitido después del cambio sobrevive
    token_nuevo = crear_token_acceso(usuario_id=1, roles=[], iat=ahora)
    with patch(
        "app.modules.usuarios.router.get_roles_vigentes",
        new=AsyncMock(return_value=[]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ac.cookies.set("access_token", token_nuevo)
            resp = await ac.get("/auth/yo")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_con_sesion_valida(mock_sesiones_auth):
    ses_dom, _ = mock_sesiones_auth
    usuario = Usuario(id=1, email="logout@example.com", nombre="Logout", password_hash="hash", activo=True)
    ses_dom.get = AsyncMock(return_value=usuario)

    token = crear_token_acceso(usuario_id=1, roles=[], iat=datetime.now(timezone.utc))
    with patch("app.modules.usuarios.router.auditar_acceso", new_callable=AsyncMock) as mock_auditar:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ac.cookies.set("access_token", token)
            resp = await ac.post("/auth/logout")
            assert resp.status_code == 200
            assert resp.json() == {"detail": "Sesión cerrada"}
            cookie = resp.headers.get("set-cookie", "")
            assert "access_token=" in cookie
            assert "max-age=0" in cookie.lower()
            assert mock_auditar.called
            registro = mock_auditar.call_args[0][1]
            assert registro.accion == "LOGOUT"
            assert registro.actor == "logout@example.com"


@pytest.mark.asyncio
async def test_logout_sin_cookie_o_token_invalido(mock_sesiones_auth):
    with patch("app.modules.usuarios.router.auditar_acceso", new_callable=AsyncMock) as mock_auditar:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Sin cookie -> 200 y no audita
            resp_sin = await ac.post("/auth/logout")
            assert resp_sin.status_code == 200
            assert not mock_auditar.called

            # 2. Token inválido -> 200 y no audita
            ac.cookies.set("access_token", "invalido")
            resp_bad = await ac.post("/auth/logout")
            assert resp_bad.status_code == 200
            assert not mock_auditar.called
