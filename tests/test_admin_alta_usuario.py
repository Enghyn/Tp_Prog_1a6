"""
Suite de `POST /usuarios` (C-12, grupo 3).

Contrato: alta de personal activo con contraseña provisoria (D3), rechazo de
email duplicado con `409 EMAIL_DUPLICADO` (D4) y contrato estricto con
`422 ERROR_VALIDACION` sin repetir secretos.

Los tests de contrato Pydantic corren sin base de datos; los HTTP usan
PostgreSQL real (regla dura #9).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.seguridad import verify_password_async
from app.modules.usuarios.models import EventoSeguridad, Usuario
from app.modules.usuarios.schemas import SolicitudAltaUsuario, UsuarioCreado
from tests.conftest import cliente_http, crear_admin_prueba

PASSWORD = "Provisoria1"


# ---------------------------------------------------------------------------
# Contrato Pydantic (sin base de datos)
# ---------------------------------------------------------------------------


def test_solicitud_alta_normaliza_email_a_minusculas_y_sin_espacios() -> None:
    solicitud = SolicitudAltaUsuario(
        email="  Nuevo.Mecanico@Taller.local ",
        nombre="Nuevo Mecánico",
        password=PASSWORD,
    )

    assert solicitud.email == "nuevo.mecanico@taller.local"


def test_solicitud_alta_recorta_el_nombre() -> None:
    solicitud = SolicitudAltaUsuario(
        email="nuevo@taller.local",
        nombre="  Nuevo Mecánico  ",
        password=PASSWORD,
    )

    assert solicitud.nombre == "Nuevo Mecánico"


def test_solicitud_alta_con_campo_extra_lanza_validation_error() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SolicitudAltaUsuario(
            email="nuevo@taller.local",
            nombre="Nuevo",
            password=PASSWORD,
            activo=False,
        )

    assert "activo" in str(excinfo.value)


def test_solicitud_alta_con_email_invalido_lanza_validation_error() -> None:
    with pytest.raises(ValidationError):
        SolicitudAltaUsuario(
            email="nuevo-taller.local", nombre="Nuevo", password=PASSWORD
        )


@pytest.mark.parametrize(
    "password",
    [
        "Corta1",  # 6 caracteres
        "provisoria1",  # sin mayúscula
        "PROVISORIA1",  # sin minúscula
        "Provisoria",  # sin dígito
        "Aa1" + "x" * 70,  # 73 caracteres
    ],
)
def test_solicitud_alta_con_password_invalida_lanza_validation_error(
    password: str,
) -> None:
    with pytest.raises(ValidationError):
        SolicitudAltaUsuario(
            email="nuevo@taller.local", nombre="Nuevo", password=password
        )


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 121])
def test_solicitud_alta_con_nombre_invalido_lanza_validation_error(
    nombre: str,
) -> None:
    with pytest.raises(ValidationError):
        SolicitudAltaUsuario(email="nuevo@taller.local", nombre=nombre, password=PASSWORD)


def test_usuario_creado_no_declara_campos_de_password() -> None:
    campos = set(UsuarioCreado.model_fields)

    assert campos == {"id", "email", "nombre", "activo", "debe_cambiar_password"}


def test_usuario_creado_rechaza_campos_extra() -> None:
    with pytest.raises(ValidationError):
        UsuarioCreado(
            id=1,
            email="nuevo@taller.local",
            nombre="Nuevo",
            activo=True,
            debe_cambiar_password=True,
            password_hash="x",
        )


# ---------------------------------------------------------------------------
# Alta exitosa (HTTP + PostgreSQL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alta_exitosa_devuelve_201_y_persiste_el_hash(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-alta@taller.test")

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            "/usuarios",
            json={
                "email": "Nuevo.Mecanico@Taller.local",
                "nombre": "Nuevo Mecánico",
                "password": PASSWORD,
            },
        )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["email"] == "nuevo.mecanico@taller.local"
    assert cuerpo["nombre"] == "Nuevo Mecánico"
    assert cuerpo["activo"] is True
    assert cuerpo["debe_cambiar_password"] is True
    assert isinstance(cuerpo["id"], int)

    usuario = (
        await contexto_auth.execute(
            select(Usuario).where(Usuario.id == cuerpo["id"])
        )
    ).scalars().first()
    assert usuario is not None
    assert usuario.password_hash != PASSWORD
    assert usuario.password_hash.startswith("$2b$")
    assert await verify_password_async(PASSWORD, usuario.password_hash) is True


@pytest.mark.asyncio
async def test_alta_no_devuelve_la_password_ni_el_hash(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-alta-secreta@taller.test")

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            "/usuarios",
            json={
                "email": "sin-secretos@taller.local",
                "nombre": "Sin Secretos",
                "password": PASSWORD,
            },
        )

    assert respuesta.status_code == 201
    assert PASSWORD not in respuesta.text
    assert "$2b$" not in respuesta.text
    assert '"password"' not in respuesta.text


@pytest.mark.asyncio
async def test_alta_audita_usuario_creado(contexto_auth) -> None:
    admin, token = await crear_admin_prueba(contexto_auth, "admin-alta-audita@taller.test")

    async with cliente_http(token) as cliente:
        await cliente.post(
            "/usuarios",
            json={
                "email": "auditado@taller.local",
                "nombre": "Auditado",
                "password": PASSWORD,
            },
        )

    eventos = (
        await contexto_auth.execute(
            select(EventoSeguridad).where(EventoSeguridad.accion == "USUARIO_CREADO")
        )
    ).scalars().all()
    assert [evento.actor for evento in eventos] == [admin.email]
    assert eventos[0].cuando is not None


# ---------------------------------------------------------------------------
# Email duplicado (D4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alta_con_email_duplicado_devuelve_409(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-duplicado@taller.test")

    async with cliente_http(token) as cliente:
        primera = await cliente.post(
            "/usuarios",
            json={
                "email": "repetido@taller.local",
                "nombre": "Repetido",
                "password": PASSWORD,
            },
        )
        segunda = await cliente.post(
            "/usuarios",
            json={
                "email": "Repetido@Taller.local",
                "nombre": "Repetido Otro",
                "password": PASSWORD,
            },
        )

    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.json() == {
        "detail": "El email ya está registrado",
        "codigo": "EMAIL_DUPLICADO",
    }

    cantidad = await contexto_auth.scalar(
        select(func.count(Usuario.id)).where(
            func.lower(Usuario.email) == "repetido@taller.local"
        )
    )
    assert cantidad == 1

    eventos = (
        await contexto_auth.execute(
            select(EventoSeguridad).where(EventoSeguridad.accion == "USUARIO_CREADO")
        )
    ).scalars().all()
    assert len(eventos) == 1


@pytest.mark.asyncio
async def test_conflicto_por_duplicado_no_revela_el_esquema(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-esquema@taller.test")

    async with cliente_http(token) as cliente:
        await cliente.post(
            "/usuarios",
            json={
                "email": "esquema@taller.local",
                "nombre": "Esquema",
                "password": PASSWORD,
            },
        )
        respuesta = await cliente.post(
            "/usuarios",
            json={
                "email": "esquema@taller.local",
                "nombre": "Esquema",
                "password": PASSWORD,
            },
        )

    assert respuesta.status_code == 409
    for fragmento in ("usuario_email_key", "ix_usuario_email", "INSERT", "usuario.email"):
        assert fragmento not in respuesta.text


# ---------------------------------------------------------------------------
# Contrato HTTP estricto (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cuerpo",
    [
        {
            "email": "extra@taller.local",
            "nombre": "Extra",
            "password": PASSWORD,
            "activo": False,
        },
        {"email": "nuevo-taller.local", "nombre": "Nuevo", "password": PASSWORD},
        {"email": "corta@taller.local", "nombre": "Corta", "password": "Corta1"},
        {"email": "sindigito@taller.local", "nombre": "Sin", "password": "Provisoria"},
        {"email": "sinmayuscula@taller.local", "nombre": "Sin", "password": "provisoria1"},
        {"email": "vacio@taller.local", "nombre": "", "password": PASSWORD},
    ],
)
async def test_alta_invalida_responde_422_y_no_crea_usuario(
    contexto_auth, cuerpo: dict
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-422@taller.test")
    total_antes = await contexto_auth.scalar(select(func.count(Usuario.id)))

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post("/usuarios", json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "ERROR_VALIDACION"
    assert respuesta.json()["detail"]

    total_despues = await contexto_auth.scalar(select(func.count(Usuario.id)))
    assert total_despues == total_antes


@pytest.mark.asyncio
async def test_la_validacion_no_repite_la_password(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-secreto@taller.test")

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            "/usuarios",
            json={
                "email": "secreto@taller.local",
                "nombre": "Secreto",
                "password": "corta",
            },
        )

    assert respuesta.status_code == 422
    assert "corta" not in respuesta.text
    assert "password" in respuesta.text


# ---------------------------------------------------------------------------
# Efecto observable: login con la contraseña provisoria
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usuario_creado_puede_iniciar_sesion_con_la_provisoria(
    contexto_auth,
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-login-nuevo@taller.test")

    async with cliente_http(token) as cliente:
        await cliente.post(
            "/usuarios",
            json={
                "email": "nuevo-login@taller.local",
                "nombre": "Nuevo Login",
                "password": PASSWORD,
            },
        )

    async with cliente_http() as cliente:
        respuesta = await cliente.post(
            "/auth/login",
            json={"email": "nuevo-login@taller.local", "password": PASSWORD},
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["debe_cambiar_password"] is True
    assert cuerpo["roles"] == []
    assert "access_token" in respuesta.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_el_alta_no_habilita_rutas_de_dominio(contexto_auth) -> None:
    """RN-06: la contraseña provisoria bloquea el dominio hasta cambiarla."""
    admin, token = await crear_admin_prueba(contexto_auth, "admin-gate@taller.test")

    async with cliente_http(token) as cliente:
        alta = await cliente.post(
            "/usuarios",
            json={
                "email": "pendiente@taller.local",
                "nombre": "Pendiente",
                "password": PASSWORD,
            },
        )
        usuario_id = alta.json()["id"]

    from tests.conftest import crear_asignacion_prueba, token_de_sesion

    await crear_asignacion_prueba(contexto_auth, usuario_id, "ADMIN")

    async with cliente_http(token_de_sesion(usuario_id)) as cliente:
        respuesta = await cliente.get("/eventos")

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"
