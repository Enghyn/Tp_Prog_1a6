import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.core.configuracion import configuracion
from app.core.database import get_session
from app.core.seguridad import hash_password_sync
from app.modules.usuarios import service as usuarios_service
from app.modules.usuarios.models import Usuario, IntentoAcceso
from app.modules.usuarios.repository import obtener_sesion_auditoria
from app.modules.usuarios.service import calcular_retry_after


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
    return Usuario(
        id=1,
        email="admin@example.com",
        nombre="Admin",
        password_hash=hash_password_sync("password123"),
        activo=True,
    )


def test_calcular_retry_after_puro():
    ahora = datetime(2026, 10, 30, 12, 0, 30, tzinfo=timezone.utc)
    # Fallo más antiguo hace 20 segundos
    fallo_antiguo = IntentoAcceso(
        id=1,
        email="test@example.com",
        ip="127.0.0.1",
        cuando=datetime(2026, 10, 30, 12, 0, 10, tzinfo=timezone.utc),
        exito=False,
    )
    # Ventana de 60s: liberación a las 12:01:10 (40s restantes desde 12:00:30)
    retry_after = calcular_retry_after([fallo_antiguo], ahora, ventana_seg=60)
    assert retry_after == 40

    # Acotado a mínimo 1 segundo
    ahora_limite = datetime(2026, 10, 30, 12, 1, 10, tzinfo=timezone.utc)
    assert calcular_retry_after([fallo_antiguo], ahora_limite, ventana_seg=60) == 1

    # Acotado a máximo ventana_seg
    ahora_previo = datetime(2026, 10, 30, 11, 0, 0, tzinfo=timezone.utc)
    assert calcular_retry_after([fallo_antiguo], ahora_previo, ventana_seg=60) == 60


@pytest.mark.asyncio
async def test_rate_limit_bloqueo_429_y_retry_after(mock_sesiones, usuario_prueba):
    ahora = datetime.now(timezone.utc)
    fallo_base = IntentoAcceso(
        id=1,
        email="admin@example.com",
        ip="127.0.0.1",
        cuando=ahora - timedelta(seconds=10),
        exito=False,
    )

    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=configuracion.login_max_intentos), \
         patch("app.modules.usuarios.service.obtener_ultimos_fallos_ventana", return_value=[fallo_base]), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock) as mock_auditar, \
         patch("app.modules.usuarios.service.verify_password_o_dummy", wraps=usuarios_service.verify_password_o_dummy) as spy_dummy:

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
            assert int(resp.headers["Retry-After"]) >= 1
            # Costo cero: no calcula ni verifica hash en petición bloqueada (Task 7.3)
            assert not spy_dummy.called
            # Auditoría registró LOGIN_BLOQUEADO sin insertar en intento_acceso (Task 7.6)
            assert mock_auditar.called
            registro = mock_auditar.call_args[0][1]
            assert registro.accion == "LOGIN_BLOQUEADO"
            assert registro.exito is None


@pytest.mark.asyncio
async def test_rate_limit_umbral_literal_quinto_falla_sexto_bloquea(mock_sesiones, usuario_prueba):
    """
    Fija la semántica acordada (D4 y decisión de governance):
    Con 4 fallos previos, el 5.º intento aún se verifica y responde 401.
    Con 5 fallos previos ya en base, el 6.º intento responde 429.
    """
    # 5.º intento (fallos previos = 4)
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=4), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp_quinto = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password_incorrecta"})
            assert resp_quinto.status_code == 401

    # 6.º intento (fallos previos = 5)
    fallo_base = IntentoAcceso(id=1, email="admin@example.com", ip="127.0.0.1", cuando=datetime.now(timezone.utc), exito=False)
    with patch("app.modules.usuarios.service.contar_intentos_fallidos", return_value=5), \
         patch("app.modules.usuarios.service.obtener_ultimos_fallos_ventana", return_value=[fallo_base]), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp_sexto = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
            assert resp_sexto.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_aislamiento_por_email_e_ip(mock_sesiones, usuario_prueba):
    """
    Los fallos de otro email o de otra IP no bloquean las credenciales válidas.
    """
    # Caso 1: misma IP, otro email tuvo 5 fallos -> este email no se bloquea
    async def contar_aislado(sesion, email, ip, desde):
        if email == "admin@example.com":
            return 0
        return 5

    with patch("app.modules.usuarios.service.contar_intentos_fallidos", side_effect=contar_aislado), \
         patch("app.modules.usuarios.service.buscar_usuario_por_email", return_value=usuario_prueba), \
         patch("app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
            assert resp.status_code == 200
