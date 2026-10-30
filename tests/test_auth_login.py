import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.modules.usuarios import service as usuarios_service
from app.core.database import get_session
from app.core.seguridad import hash_password_sync
from app.modules.usuarios.models import Usuario, AsignacionRol
from app.modules.usuarios.repository import obtener_sesion_auditoria


@pytest.fixture
def mock_sesiones():
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


@pytest.fixture
def usuario_prueba():
    ahora = datetime.now(timezone.utc)
    return Usuario(
        id=1,
        email="admin@example.com",
        nombre="Administrador",
        password_hash=hash_password_sync("password123"),
        activo=True,
        debe_cambiar_password=False,
        asignaciones=[
            AsignacionRol(id=1, usuario_id=1, rol="ADMIN", desde=ahora, revocada_en=None, vence_en=None),
        ],
    )


@pytest.mark.asyncio
async def test_login_exitoso_setea_cookie_httponly(mock_sesiones, usuario_prueba):
    ses_dominio, _ = mock_sesiones
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock) as mock_auditar:

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
            assert resp.status_code == 200
            cookie_header = resp.headers.get("set-cookie", "")
            assert "access_token=" in cookie_header
            assert "httponly" in cookie_header.lower()
            assert "samesite=lax" in cookie_header.lower()
            assert "path=/" in cookie_header.lower()
            assert mock_auditar.called


@pytest.mark.asyncio
async def test_login_exitoso_cuerpo_respuesta(mock_sesiones, usuario_prueba):
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["usuario"]["id"] == 1
            assert data["usuario"]["email"] == "admin@example.com"
            assert data["usuario"]["nombre"] == "Administrador"
            assert data["usuario"]["debe_cambiar_password"] is False
            assert "password_hash" not in data["usuario"]
            assert data["roles"] == ["ADMIN"]
            assert "token" in data
            assert "iat" in data["token"]
            assert "exp" in data["token"]


@pytest.mark.asyncio
async def test_login_contrato_estricto_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Campo extra no declarado
        r_extra = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123", "campo_extra": "hack"})
        assert r_extra.status_code == 422
        assert "access_token=" not in r_extra.headers.get("set-cookie", "")

        # Email inválido
        r_email = await ac.post("/auth/login", json={"email": "no-es-un-email", "password": "password123"})
        assert r_email.status_code == 422

        # Contraseña vacía
        r_pass_vacia = await ac.post("/auth/login", json={"email": "admin@example.com", "password": ""})
        assert r_pass_vacia.status_code == 422

        # Contraseña > 72 caracteres
        r_pass_larga = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "a" * 73})
        assert r_pass_larga.status_code == 422


@pytest.mark.asyncio
async def test_login_roles_vigentes_filtra_revocados_y_vencidos(mock_sesiones):
    ahora = datetime.now(timezone.utc)
    usuario_con_roles = Usuario(
        id=2,
        email="mecanico@example.com",
        nombre="Mecánico",
        password_hash=hash_password_sync("password123"),
        activo=True,
        debe_cambiar_password=False,
        asignaciones=[
            AsignacionRol(id=1, usuario_id=2, rol="MECANICO", desde=ahora, revocada_en=None, vence_en=None),
            AsignacionRol(id=2, usuario_id=2, rol="ADMIN", desde=ahora, revocada_en=ahora, vence_en=None),  # Revocado
            AsignacionRol(id=3, usuario_id=2, rol="RECEPCION", desde=ahora, revocada_en=None, vence_en=ahora - timedelta(days=1)),  # Vencido
        ],
    )

    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_con_roles), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "mecanico@example.com", "password": "password123"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["roles"] == ["MECANICO"]


@pytest.mark.asyncio
async def test_login_password_incorrecta_devuelve_401(mock_sesiones, usuario_prueba):
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock) as mock_auditar:

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password_erronea"})
            assert resp.status_code == 401
            assert "access_token=" not in resp.headers.get("set-cookie", "")
            data = resp.json()
            assert data["detail"] == "Credenciales inválidas"
            assert data["codigo"] == "CREDENCIALES_INVALIDAS"
            assert mock_auditar.called
            registro = mock_auditar.call_args[0][1]
            assert registro.accion == "LOGIN_FALLIDO"
            assert registro.exito is False


@pytest.mark.asyncio
async def test_login_opaco_email_inexistente_vs_password_erronea_son_identicos(mock_sesiones, usuario_prueba):
    # 1. Contraseña errónea con usuario existente
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp_pass_mala = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "bad_password"})

    # 2. Email inexistente
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=None), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp_email_inexistente = await ac.post("/auth/login", json={"email": "inexistente@example.com", "password": "bad_password"})

    assert resp_pass_mala.status_code == resp_email_inexistente.status_code == 401
    assert resp_pass_mala.json() == resp_email_inexistente.json()
    assert resp_pass_mala.headers.get("set-cookie") == resp_email_inexistente.headers.get("set-cookie") is None


@pytest.mark.asyncio
async def test_login_usuario_inactivo_devuelve_401_identico(mock_sesiones):
    usuario_inactivo = Usuario(
        id=3,
        email="inactivo@example.com",
        nombre="Inactivo",
        password_hash=hash_password_sync("password123"),
        activo=False,
        debe_cambiar_password=False,
    )
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_inactivo), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock) as mock_auditar:

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "inactivo@example.com", "password": "password123"})
            assert resp.status_code == 401
            assert resp.json() == {"detail": "Credenciales inválidas", "codigo": "CREDENCIALES_INVALIDAS"}
            assert "access_token=" not in resp.headers.get("set-cookie", "")
            assert mock_auditar.called
            assert mock_auditar.call_args[0][1].accion == "LOGIN_FALLIDO"


@pytest.mark.asyncio
async def test_login_dummy_hash_ejecutado_cuando_usuario_no_existe(mock_sesiones):
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=0), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=None), \
         patch("app.modules.usuarios.service.verify_password_o_dummy", wraps=usuarios_service.verify_password_o_dummy) as spy_dummy, \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "fantasma@example.com", "password": "password123"})
            assert resp.status_code == 401
            assert spy_dummy.called
            # Verifica que hash_real fue None, activando el dummy hash
            assert spy_dummy.call_args[0][1] is None
