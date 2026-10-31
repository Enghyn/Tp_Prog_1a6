"""
Suite de `POST /auth/cambiar-password` (C-11).

Matriz de cobertura requisito → test (delta `autenticacion-sesion`):

ADDED — Cambio de contraseña autenticado
- Cambio exitoso persiste el nuevo estado →
  `test_cambiar_password_exitoso_actualiza_hash_timestamp_y_bandera`,
  `test_cambiar_password_persiste_en_postgresql_real`
- La respuesta no reemite la cookie de sesión →
  `test_cambiar_password_http_exitoso_sin_reemitir_cookie`
- Usuario con contraseña provisoria puede cambiar →
  `test_cambiar_password_usuario_provisorio_no_se_bloquea_y_limpia_bandera`,
  `test_cambiar_password_http_usuario_provisorio_recibe_200`
- El token anterior deja de ser válido →
  `test_cambiar_password_invalida_el_token_anterior`
- Un token emitido después del cambio es válido →
  `test_token_emitido_despues_del_cambio_es_valido`

ADDED — Rechazo del cambio de contraseña
- Contraseña actual incorrecta →
  `test_cambiar_password_con_actual_incorrecta_lanza_no_autenticado_sin_escribir`,
  `test_cambiar_password_http_con_actual_incorrecta_devuelve_401`
- Contrato de entrada estricto →
  `test_solicitud_cambio_password_sin_password_actual_lanza_validation_error`,
  `test_solicitud_cambio_password_sin_password_nueva_lanza_validation_error`,
  `test_solicitud_cambio_password_con_campo_extra_lanza_validation_error`,
  `test_cambiar_password_http_campo_extra_devuelve_422`
- Longitud fuera de rango →
  `test_solicitud_cambio_password_nueva_de_7_caracteres_lanza_validation_error`,
  `test_solicitud_cambio_password_nueva_de_73_caracteres_lanza_validation_error`,
  `test_solicitud_cambio_password_nueva_de_8_caracteres_validos_no_lanza`,
  `test_solicitud_cambio_password_nueva_de_72_caracteres_validos_no_lanza`
- Complejidad insuficiente →
  `test_solicitud_cambio_password_nueva_sin_mayuscula_lanza_validation_error`,
  `test_solicitud_cambio_password_nueva_sin_minuscula_lanza_validation_error`,
  `test_solicitud_cambio_password_nueva_sin_digito_lanza_validation_error`,
  `test_validar_complejidad_password_invalida_lanza_value_error`
- La contraseña nueva repite la actual →
  `test_solicitud_cambio_password_nueva_igual_a_la_actual_lanza_validation_error`
- Petición sin sesión →
  `test_cambiar_password_sin_cookie_devuelve_401_aunque_el_body_sea_invalido`
- La respuesta 422 no repite las contraseñas →
  `test_cambiar_password_422_no_repite_las_contrasenas`,
  `test_cambiar_password_422_conserva_loc_msg_y_type`,
  `test_login_422_no_repite_la_contrasena`

MODIFIED — Auditoría de acceso en transacción independiente
- Cambio de contraseña auditado →
  `test_cambiar_password_exitoso_audita_una_vez_sin_intento_acceso`,
  `test_cambiar_password_audita_evento_y_no_inserta_intento_acceso`
- Login fallido / exitoso / bloqueado y logout → tests preexistentes de
  `tests/test_auth_auditoria.py` y `tests/test_auth_sesion.py`.

RN-07 con precisión de microsegundos (sin redondeos) →
`test_token_con_iat_un_microsegundo_antes_del_cambio_es_rechazado`,
`test_token_con_iat_igual_al_cambio_es_aceptado`.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.dependencies import SesionActual, obtener_usuario_actual
from app.core.errors import NoAutenticadoError
from app.core.seguridad import hash_password_sync
from app.modules.usuarios.models import EventoSeguridad, IntentoAcceso, Usuario
from app.modules.usuarios.repository import (
    actualizar_password,
    obtener_sesion_auditoria,
    obtener_sesion_cambio_password,
)
from app.modules.usuarios.schemas import (
    SolicitudCambioPassword,
    validar_complejidad_password,
)
from app.modules.usuarios.service import cambiar_password
from main import app

ACTUAL = "Provisoria1"
NUEVA = "NuevaClave2"


class ResultadoFalso:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class ContextoTransaccionEspia:
    def __init__(self, sesion: "SesionEspia") -> None:
        self.sesion = sesion

    async def __aenter__(self) -> "SesionEspia":
        self.sesion.transacciones_abiertas += 1
        return self.sesion

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.sesion.transacciones_abiertas -= 1
        return False


class SesionEspia:
    """Doble de sesión para verificar contratos sin abrir PostgreSQL."""

    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.sentencias: list = []
        self.agregados: list = []
        self.transacciones_abiertas = 0
        self.flushes = 0
        self.commit_llamado = False
        self.cerrada = False

    def begin(self) -> ContextoTransaccionEspia:
        return ContextoTransaccionEspia(self)

    async def execute(self, sentencia):
        self.sentencias.append(sentencia)
        return ResultadoFalso(self.rowcount)

    async def flush(self) -> None:
        self.flushes += 1

    def add(self, item) -> None:
        self.agregados.append(item)

    async def commit(self) -> None:
        self.commit_llamado = True

    async def close(self) -> None:
        self.cerrada = True


class FabricaSesionesFalsa:
    def __init__(self) -> None:
        self.abiertas = 0

    def __call__(self):
        fabrica = self

        class ContextoFalso:
            async def __aenter__(self):
                fabrica.abiertas += 1
                return "sesion-falsa"

            async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
                return False

        return ContextoFalso()


# ---------------------------------------------------------------------------
# Grupo 2 — Schema de entrada (Pydantic directo, sin HTTP)
# ---------------------------------------------------------------------------


def test_solicitud_cambio_password_sin_password_actual_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_nueva=NUEVA)


def test_solicitud_cambio_password_sin_password_nueva_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL)


def test_solicitud_cambio_password_con_campo_extra_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            campo_extra="no permitido",
        )


def test_solicitud_cambio_password_nueva_de_7_caracteres_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="Nueva12")


def test_solicitud_cambio_password_nueva_de_73_caracteres_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="A" + "a1" * 36)


def test_solicitud_cambio_password_nueva_sin_mayuscula_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="nuevaclave2")


def test_solicitud_cambio_password_nueva_sin_minuscula_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="NUEVACLAVE2")


def test_solicitud_cambio_password_nueva_sin_digito_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="NuevaClave")


def test_solicitud_cambio_password_nueva_igual_a_la_actual_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudCambioPassword(password_actual=NUEVA, password_nueva=NUEVA)


# --- Triangular: bordes y no normalización ---------------------------------


def test_solicitud_cambio_password_nueva_de_8_caracteres_validos_no_lanza() -> None:
    solicitud = SolicitudCambioPassword(password_actual=ACTUAL, password_nueva="Nueva123")

    assert solicitud.password_nueva == "Nueva123"


def test_solicitud_cambio_password_nueva_de_72_caracteres_validos_no_lanza() -> None:
    nueva = "Aa1" + "x" * 69

    solicitud = SolicitudCambioPassword(password_actual=ACTUAL, password_nueva=nueva)

    assert solicitud.password_nueva == nueva
    assert len(solicitud.password_nueva) == 72


def test_solicitud_cambio_password_actual_con_espacios_conserva_el_valor_exacto() -> None:
    solicitud = SolicitudCambioPassword(
        password_actual="  Clave 1  ",
        password_nueva=NUEVA,
    )

    assert solicitud.password_actual == "  Clave 1  "


def test_solicitud_cambio_password_nueva_con_espacios_internos_es_valida() -> None:
    solicitud = SolicitudCambioPassword(
        password_actual=ACTUAL,
        password_nueva="Nueva Clave2",
    )

    assert solicitud.password_nueva == "Nueva Clave2"


# --- Refactor: helper puro de complejidad (2.4) ----------------------------


def test_validar_complejidad_password_valida_retorna_el_mismo_valor() -> None:
    assert validar_complejidad_password("Nueva Clave2") == "Nueva Clave2"


@pytest.mark.parametrize(
    "valor",
    [
        "nuevaclave2",
        "NUEVACLAVE2",
        "NuevaClave",
        "nuevaclave2Á",
    ],
)
def test_validar_complejidad_password_invalida_lanza_value_error(valor: str) -> None:
    with pytest.raises(ValueError):
        validar_complejidad_password(valor)


# ---------------------------------------------------------------------------
# Grupo 3 — Repositorio y sesión dedicada
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actualizar_password_actualiza_las_tres_columnas(contexto_auth) -> None:
    usuario = Usuario(
        email="cambio-repo@example.com",
        nombre="Repo",
        password_hash=hash_password_sync(ACTUAL),
        debe_cambiar_password=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.flush()
    cambiada_en = datetime(2026, 10, 31, 12, 0, 0, 123456, tzinfo=timezone.utc)

    filas = await actualizar_password(
        contexto_auth,
        usuario_id=usuario.id,
        password_hash="hash-nuevo",
        cambiada_en=cambiada_en,
    )

    assert filas == 1
    await contexto_auth.refresh(usuario)
    assert usuario.password_hash == "hash-nuevo"
    assert usuario.password_cambiada_en == cambiada_en
    assert usuario.debe_cambiar_password is False


@pytest.mark.asyncio
async def test_actualizar_password_usuario_inexistente_lanza_no_autenticado(
    contexto_auth,
) -> None:
    with pytest.raises(NoAutenticadoError) as excinfo:
        await actualizar_password(
            contexto_auth,
            usuario_id=999_999_999,
            password_hash="hash-nuevo",
            cambiada_en=datetime.now(timezone.utc),
        )

    assert excinfo.value.codigo == "CREDENCIALES_INVALIDAS"


@pytest.mark.asyncio
async def test_actualizar_password_revierte_si_la_transaccion_falla(
    contexto_auth,
) -> None:
    hash_original = hash_password_sync(ACTUAL)
    usuario = Usuario(
        email="cambio-rollback@example.com",
        nombre="Rollback",
        password_hash=hash_original,
        debe_cambiar_password=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()

    with pytest.raises(RuntimeError):
        async with contexto_auth.begin():
            await actualizar_password(
                contexto_auth,
                usuario_id=usuario.id,
                password_hash="hash-nuevo",
                cambiada_en=datetime.now(timezone.utc),
            )
            raise RuntimeError("fallo simulado después del UPDATE")

    await contexto_auth.refresh(usuario)
    assert usuario.password_hash == hash_original
    assert usuario.debe_cambiar_password is True


@pytest.mark.asyncio
async def test_actualizar_password_no_hace_commit_ni_cierra_la_sesion() -> None:
    sesion = SesionEspia()

    await actualizar_password(
        sesion,
        usuario_id=1,
        password_hash="hash-nuevo",
        cambiada_en=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert sesion.commit_llamado is False
    assert sesion.cerrada is False
    assert sesion.flushes == 1
    assert len(sesion.sentencias) == 1


@pytest.mark.asyncio
async def test_actualizar_password_sin_filas_afectadas_lanza_no_autenticado() -> None:
    sesion = SesionEspia(rowcount=0)

    with pytest.raises(NoAutenticadoError):
        await actualizar_password(
            sesion,
            usuario_id=1,
            password_hash="hash-nuevo",
            cambiada_en=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_obtener_sesion_cambio_password_usa_el_session_maker_del_app_state() -> None:
    fabrica = FabricaSesionesFalsa()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_maker=fabrica))
    )

    generador = obtener_sesion_cambio_password(request)
    sesion = await generador.__anext__()

    assert sesion == "sesion-falsa"
    assert fabrica.abiertas == 1
    with pytest.raises(StopAsyncIteration):
        await generador.__anext__()


# ---------------------------------------------------------------------------
# Grupo 4 — Servicio (`cambiar_password`)
# ---------------------------------------------------------------------------


def _usuario(password: str = ACTUAL, debe_cambiar: bool = False) -> Usuario:
    return Usuario(
        id=42,
        email="servicio-cambio@example.com",
        nombre="Servicio",
        password_hash=hash_password_sync(password),
        activo=True,
        debe_cambiar_password=debe_cambiar,
    )


def _parametros_update(sesion: SesionEspia) -> dict:
    return sesion.sentencias[0].compile().params


@pytest.mark.asyncio
async def test_cambiar_password_con_actual_incorrecta_lanza_no_autenticado_sin_escribir() -> None:
    sesion = SesionEspia()

    with pytest.raises(NoAutenticadoError) as excinfo:
        await cambiar_password(
            usuario=_usuario(),
            password_actual="Incorrecta1",
            password_nueva=NUEVA,
            ip="10.0.0.1",
            sesion_cambio=sesion,
            sesion_auditoria=sesion,
        )

    assert excinfo.value.codigo == "CREDENCIALES_INVALIDAS"
    assert sesion.sentencias == []
    assert sesion.agregados == []
    assert sesion.transacciones_abiertas == 0


@pytest.mark.asyncio
async def test_cambiar_password_exitoso_actualiza_hash_timestamp_y_bandera() -> None:
    sesion = SesionEspia()
    instante = datetime(2026, 10, 31, 12, 0, 0, 123456, tzinfo=timezone.utc)

    with patch("app.modules.usuarios.service._ahora", return_value=instante):
        respuesta = await cambiar_password(
            usuario=_usuario(),
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            ip="10.0.0.1",
            sesion_cambio=sesion,
            sesion_auditoria=sesion,
        )

    assert respuesta.detail == "Contraseña actualizada"
    parametros = _parametros_update(sesion)
    assert bcrypt.checkpw(NUEVA.encode("utf-8"), parametros["password_hash"].encode("utf-8"))
    assert parametros["password_cambiada_en"] == instante
    assert parametros["debe_cambiar_password"] is False
    assert sesion.commit_llamado is False
    assert sesion.transacciones_abiertas == 0


@pytest.mark.asyncio
async def test_cambiar_password_exitoso_audita_una_vez_sin_intento_acceso() -> None:
    sesion = SesionEspia()

    await cambiar_password(
        usuario=_usuario(),
        password_actual=ACTUAL,
        password_nueva=NUEVA,
        ip="10.0.0.1",
        sesion_cambio=sesion,
        sesion_auditoria=sesion,
    )

    assert len(sesion.agregados) == 1
    evento = sesion.agregados[0]
    assert isinstance(evento, EventoSeguridad)
    assert evento.accion == "PASSWORD_CAMBIADA"
    assert evento.actor == "servicio-cambio@example.com"
    assert not any(isinstance(item, IntentoAcceso) for item in sesion.agregados)


@pytest.mark.asyncio
async def test_cambiar_password_usa_el_reloj_fijo_sin_truncar_microsegundos() -> None:
    sesion = SesionEspia()
    instante = datetime(2026, 10, 31, 23, 59, 59, 987654, tzinfo=timezone.utc)

    with patch("app.modules.usuarios.service._ahora", return_value=instante):
        await cambiar_password(
            usuario=_usuario(),
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            ip="10.0.0.1",
            sesion_cambio=sesion,
            sesion_auditoria=sesion,
        )

    assert _parametros_update(sesion)["password_cambiada_en"] == instante
    assert sesion.agregados[0].cuando == instante


@pytest.mark.asyncio
async def test_cambiar_password_propaga_la_ip_a_la_auditoria() -> None:
    sesion = SesionEspia()

    with patch(
        "app.modules.usuarios.service.auditar_acceso", new_callable=AsyncMock
    ) as mock_auditar:
        await cambiar_password(
            usuario=_usuario(),
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            ip="203.0.113.7",
            sesion_cambio=sesion,
            sesion_auditoria=sesion,
        )

    registro = mock_auditar.call_args[0][1]
    assert registro.ip == "203.0.113.7"


@pytest.mark.asyncio
async def test_cambiar_password_propaga_el_fallo_de_auditoria() -> None:
    sesion = SesionEspia()

    with patch(
        "app.modules.usuarios.service.auditar_acceso",
        new_callable=AsyncMock,
        side_effect=RuntimeError("auditoría caída"),
    ):
        with pytest.raises(RuntimeError):
            await cambiar_password(
                usuario=_usuario(),
                password_actual=ACTUAL,
                password_nueva=NUEVA,
                ip="10.0.0.1",
                sesion_cambio=sesion,
                sesion_auditoria=sesion,
            )

    assert len(sesion.sentencias) == 1


@pytest.mark.asyncio
async def test_cambiar_password_usuario_provisorio_no_se_bloquea_y_limpia_bandera() -> None:
    sesion = SesionEspia()

    await cambiar_password(
        usuario=_usuario(debe_cambiar=True),
        password_actual=ACTUAL,
        password_nueva=NUEVA,
        ip="10.0.0.1",
        sesion_cambio=sesion,
        sesion_auditoria=sesion,
    )

    assert _parametros_update(sesion)["debe_cambiar_password"] is False


@pytest.mark.asyncio
async def test_cambiar_password_persiste_en_postgresql_real(contexto_auth) -> None:
    usuario = Usuario(
        email="servicio-persistencia@example.com",
        nombre="Persistencia",
        password_hash=hash_password_sync(ACTUAL),
        activo=True,
        debe_cambiar_password=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()
    instante = datetime(2026, 10, 31, 12, 0, 0, 654321, tzinfo=timezone.utc)

    with patch("app.modules.usuarios.service._ahora", return_value=instante):
        respuesta = await cambiar_password(
            usuario=usuario,
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            ip="10.0.0.1",
            sesion_cambio=contexto_auth,
            sesion_auditoria=contexto_auth,
        )

    assert respuesta.detail == "Contraseña actualizada"
    await contexto_auth.refresh(usuario)
    assert usuario.debe_cambiar_password is False
    assert usuario.password_cambiada_en == instante
    assert bcrypt.checkpw(NUEVA.encode("utf-8"), usuario.password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Grupo 5 — Endpoint HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def contexto_http_sin_base():
    """
    Autentica la petición y entrega sesiones dobles para probar solo el
    contrato HTTP (validación y forma del error), sin abrir PostgreSQL.
    """
    usuario = Usuario(
        id=7,
        email="contrato@example.com",
        nombre="Contrato",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    sesion_actual = SesionActual(
        usuario=usuario,
        iat=datetime.now(timezone.utc),
        exp=0,
    )
    sesion = SesionEspia()

    async def override_usuario_actual() -> SesionActual:
        return sesion_actual

    async def override_sesion_cambio():
        yield sesion

    async def override_sesion_auditoria():
        yield sesion

    app.dependency_overrides[obtener_usuario_actual] = override_usuario_actual
    app.dependency_overrides[obtener_sesion_cambio_password] = override_sesion_cambio
    app.dependency_overrides[obtener_sesion_auditoria] = override_sesion_auditoria
    try:
        yield
    finally:
        app.dependency_overrides.clear()


async def _login(cliente: AsyncClient, email: str, password: str):
    return await cliente.post(
        "/auth/login", json={"email": email, "password": password}
    )


async def _crear_usuario_http(
    contexto_auth,
    email: str,
    password: str,
    debe_cambiar_password: bool = False,
) -> Usuario:
    usuario = Usuario(
        email=email,
        nombre="HTTP",
        password_hash=hash_password_sync(password),
        activo=True,
        debe_cambiar_password=debe_cambiar_password,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()
    return usuario


@pytest.mark.asyncio
async def test_cambiar_password_sin_cookie_devuelve_401_aunque_el_body_sea_invalido() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        respuesta = await cliente.post(
            "/auth/cambiar-password", json={"campo_no_declarado": "x"}
        )

    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "detail": "Credenciales inválidas",
        "codigo": "CREDENCIALES_INVALIDAS",
    }


@pytest.mark.asyncio
async def test_cambiar_password_422_no_repite_las_contrasenas(contexto_http_sin_base) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={
                "password_actual": "ActualSecreta1",
                "password_nueva": "corta",
            },
        )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "ERROR_VALIDACION"
    assert "ActualSecreta1" not in respuesta.text
    assert "corta" not in respuesta.text


@pytest.mark.asyncio
async def test_cambiar_password_422_conserva_loc_msg_y_type(contexto_http_sin_base) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={"password_actual": "ActualSecreta1", "password_nueva": "corta"},
        )

    errores = respuesta.json()["detail"]
    assert errores
    for error in errores:
        assert set(error) == {"loc", "msg", "type"}
    assert errores[0]["loc"] == ["body", "password_nueva"]


@pytest.mark.asyncio
async def test_login_422_no_repite_la_contrasena() -> None:
    valor = "x" * 73

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        respuesta = await cliente.post(
            "/auth/login", json={"email": "a@b.com", "password": valor}
        )

    assert respuesta.status_code == 422
    assert valor not in respuesta.text
    assert set(respuesta.json()["detail"][0]) == {"loc", "msg", "type"}


@pytest.mark.asyncio
async def test_cambiar_password_http_exitoso_sin_reemitir_cookie(contexto_auth) -> None:
    usuario = await _crear_usuario_http(
        contexto_auth, "http-cambio@example.com", ACTUAL
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        assert (await _login(cliente, usuario.email, ACTUAL)).status_code == 200
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={"password_actual": ACTUAL, "password_nueva": NUEVA},
        )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"detail": "Contraseña actualizada"}
    assert "access_token=" not in respuesta.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_cambiar_password_http_con_actual_incorrecta_devuelve_401(contexto_auth) -> None:
    usuario = await _crear_usuario_http(
        contexto_auth, "http-401@example.com", ACTUAL
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        assert (await _login(cliente, usuario.email, ACTUAL)).status_code == 200
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={"password_actual": "Incorrecta1", "password_nueva": NUEVA},
        )

    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "detail": "Credenciales inválidas",
        "codigo": "CREDENCIALES_INVALIDAS",
    }
    await contexto_auth.refresh(usuario)
    assert bcrypt.checkpw(ACTUAL.encode("utf-8"), usuario.password_hash.encode("utf-8"))


@pytest.mark.asyncio
async def test_cambiar_password_http_campo_extra_devuelve_422(contexto_auth) -> None:
    usuario = await _crear_usuario_http(
        contexto_auth, "http-extra@example.com", ACTUAL
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        assert (await _login(cliente, usuario.email, ACTUAL)).status_code == 200
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={
                "password_actual": ACTUAL,
                "password_nueva": NUEVA,
                "campo_extra": "x",
            },
        )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "ERROR_VALIDACION"


@pytest.mark.asyncio
async def test_cambiar_password_http_usuario_provisorio_recibe_200(contexto_auth) -> None:
    usuario = await _crear_usuario_http(
        contexto_auth,
        "http-provisorio@example.com",
        ACTUAL,
        debe_cambiar_password=True,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        assert (await _login(cliente, usuario.email, ACTUAL)).status_code == 200
        respuesta = await cliente.post(
            "/auth/cambiar-password",
            json={"password_actual": ACTUAL, "password_nueva": NUEVA},
        )

    assert respuesta.status_code == 200
    await contexto_auth.refresh(usuario)
    assert usuario.debe_cambiar_password is False


# ---------------------------------------------------------------------------
# Grupo 7 — Auditoría `PASSWORD_CAMBIADA`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cambiar_password_audita_evento_y_no_inserta_intento_acceso(
    contexto_auth,
) -> None:
    usuario = Usuario(
        email="auditoria-cambio@example.com",
        nombre="Auditoría",
        password_hash=hash_password_sync(ACTUAL),
        activo=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()
    instante = datetime(2026, 10, 31, 12, 0, 0, 111222, tzinfo=timezone.utc)

    with patch("app.modules.usuarios.service._ahora", return_value=instante):
        await cambiar_password(
            usuario=usuario,
            password_actual=ACTUAL,
            password_nueva=NUEVA,
            ip="198.51.100.9",
            sesion_cambio=contexto_auth,
            sesion_auditoria=contexto_auth,
        )

    eventos = (
        await contexto_auth.execute(
            select(EventoSeguridad).where(EventoSeguridad.actor == usuario.email)
        )
    ).scalars().all()
    intentos = (
        await contexto_auth.execute(
            select(IntentoAcceso).where(IntentoAcceso.email == usuario.email)
        )
    ).scalars().all()

    assert len(eventos) == 1
    assert eventos[0].accion == "PASSWORD_CAMBIADA"
    assert eventos[0].cuando == instante
    assert intentos == []


@pytest.mark.asyncio
async def test_cambiar_password_fallo_de_auditoria_propaga_y_persiste_el_cambio(
    contexto_auth,
) -> None:
    usuario = Usuario(
        email="auditoria-fallo@example.com",
        nombre="Auditoría fallo",
        password_hash=hash_password_sync(ACTUAL),
        activo=True,
        debe_cambiar_password=True,
    )
    contexto_auth.add(usuario)
    await contexto_auth.commit()

    with patch(
        "app.modules.usuarios.service.auditar_acceso",
        new_callable=AsyncMock,
        side_effect=RuntimeError("auditoría caída"),
    ):
        with pytest.raises(RuntimeError):
            await cambiar_password(
                usuario=usuario,
                password_actual=ACTUAL,
                password_nueva=NUEVA,
                ip="198.51.100.9",
                sesion_cambio=contexto_auth,
                sesion_auditoria=contexto_auth,
            )

    await contexto_auth.refresh(usuario)
    assert usuario.debe_cambiar_password is False
    assert bcrypt.checkpw(NUEVA.encode("utf-8"), usuario.password_hash.encode("utf-8"))
