import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario
from app.modules.clientes.models import Cliente as ClienteModel
from app.modules.usuarios.schemas import SolicitudRegistro, UsuarioRegistrado
from tests.conftest import cliente_http, crear_admin_prueba

PASSWORD = "Password123"


# ---------------------------------------------------------------------------
# Contrato Pydantic (sin base de datos)
# ---------------------------------------------------------------------------


def test_solicitud_registro_campos() -> None:
    campos = set(SolicitudRegistro.model_fields)
    assert campos == {"email", "nombre", "password", "documento", "telefono"}


def test_usuario_registrado_campos() -> None:
    campos = set(UsuarioRegistrado.model_fields)
    assert campos == {"id", "email", "nombre", "activo", "debe_cambiar_password", "cliente_id"}


def test_solicitud_registro_normaliza_email() -> None:
    s = SolicitudRegistro(
        email="  Nuevo@Taller.local ", nombre="Nuevo", password=PASSWORD,
        documento="DOC", telefono="123",
    )
    assert s.email == "nuevo@taller.local"


def test_solicitud_registro_recorta_nombre() -> None:
    s = SolicitudRegistro(
        email="nuevo@taller.local", nombre="  Nuevo  ", password=PASSWORD,
        documento="DOC", telefono="123",
    )
    assert s.nombre == "Nuevo"


def test_solicitud_registro_campo_extra() -> None:
    with pytest.raises(ValidationError):
        SolicitudRegistro(
            email="nuevo@taller.local", nombre="Nuevo", password=PASSWORD,
            documento="DOC", telefono="123", extra=True,
        )


def test_solicitud_registro_password_invalida() -> None:
    for pwd in ["Corta1", "sinmayuscula1", "SINMINUSCULA1", "SinDigito", "Aa1" + "x" * 70]:
        with pytest.raises(ValidationError):
            SolicitudRegistro(
                email="nuevo@taller.local", nombre="Nuevo", password=pwd,
                documento="DOC", telefono="123",
            )


@pytest.mark.parametrize("campo", ["nombre", "documento", "telefono"])
def test_solicitud_registro_campo_vacio(campo: str) -> None:
    kwargs = dict(email="nuevo@taller.local", nombre="Nuevo", password=PASSWORD, documento="DOC", telefono="123")
    kwargs[campo] = "   "
    with pytest.raises(ValidationError):
        SolicitudRegistro(**kwargs)


@pytest.mark.parametrize("campo,limite", [("nombre", 121), ("documento", 41), ("telefono", 41)])
def test_solicitud_registro_campo_largo(campo: str, limite: int) -> None:
    kwargs = dict(email="nuevo@taller.local", nombre="Nuevo", password=PASSWORD, documento="DOC", telefono="123")
    kwargs[campo] = "x" * limite
    with pytest.raises(ValidationError):
        SolicitudRegistro(**kwargs)


def test_usuario_registrado_rechaza_password_hash() -> None:
    with pytest.raises(ValidationError):
        UsuarioRegistrado(
            id=1, email="a@b.com", nombre="N", activo=True,
            debe_cambiar_password=False, cliente_id=1, password_hash="x",
        )


# ---------------------------------------------------------------------------
# HTTP + PostgreSQL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registro_exitoso_201_y_persistencia(contexto_auth) -> None:
    async with cliente_http() as c:
        r = await c.post(
            "/auth/registro",
            json={
                "email": "Nuevo@Taller.local",
                "nombre": "Nuevo Cliente",
                "password": PASSWORD,
                "documento": "DOC-REG-1",
                "telefono": "123456",
            },
        )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["email"] == "nuevo@taller.local"
    assert cuerpo["nombre"] == "Nuevo Cliente"
    assert cuerpo["activo"] is True
    assert cuerpo["debe_cambiar_password"] is False
    assert isinstance(cuerpo["id"], int)
    assert isinstance(cuerpo["cliente_id"], int)
    assert "password_hash" not in cuerpo
    assert "$2b$" not in r.text

    usuario = (await contexto_auth.execute(select(Usuario).where(Usuario.id == cuerpo["id"]))).scalars().first()
    assert usuario is not None
    assert usuario.password_hash.startswith("$2b$")
    assert usuario.debe_cambiar_password is False

    cliente = (await contexto_auth.execute(select(ClienteModel).where(ClienteModel.id == cuerpo["cliente_id"]))).scalars().first()
    assert cliente is not None
    assert cliente.usuario_id == usuario.id
    assert cliente.documento == "DOC-REG-1"

    asignaciones = (await contexto_auth.execute(
        select(AsignacionRol).where(AsignacionRol.usuario_id == usuario.id)
    )).scalars().all()
    assert any(a.rol == "CLIENTE" and a.revocada_en is None for a in asignaciones)

    eventos = (await contexto_auth.execute(
        select(EventoSeguridad).where(EventoSeguridad.accion == "USUARIO_AUTO_REGISTRADO")
    )).scalars().all()
    assert any(e.actor == "nuevo@taller.local" for e in eventos)


@pytest.mark.asyncio
async def test_registro_login_inmediato(contexto_auth) -> None:
    async with cliente_http() as c:
        await c.post(
            "/auth/registro",
            json={
                "email": "logininm@taller.local",
                "nombre": "Login Inm",
                "password": PASSWORD,
                "documento": "DOC-REG-2",
                "telefono": "123456",
            },
        )
        r = await c.post("/auth/login", json={"email": "logininm@taller.local", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["usuario"]["debe_cambiar_password"] is False
    assert "CLIENTE" in r.json()["roles"]


@pytest.mark.asyncio
async def test_registro_email_duplicado_409_sin_residuos(contexto_auth) -> None:
    async with cliente_http() as c:
        primera = await c.post(
            "/auth/registro",
            json={
                "email": "dup@taller.local",
                "nombre": "Dup",
                "password": PASSWORD,
                "documento": "DOC-DUP-1",
                "telefono": "123456",
            },
        )
        segunda = await c.post(
            "/auth/registro",
            json={
                "email": "Dup@Taller.local",
                "nombre": "Dup2",
                "password": PASSWORD,
                "documento": "DOC-DUP-2",
                "telefono": "123456",
            },
        )
    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.json()["codigo"] == "EMAIL_DUPLICADO"

    count_u = await contexto_auth.scalar(select(func.count(Usuario.id)).where(func.lower(Usuario.email) == "dup@taller.local"))
    assert count_u == 1
    count_c = await contexto_auth.scalar(select(func.count(ClienteModel.id)).where(ClienteModel.documento.in_(["DOC-DUP-1", "DOC-DUP-2"])))
    # solo el primero persiste
    assert count_c == 1


@pytest.mark.asyncio
async def test_registro_documento_duplicado_409_sin_residuos(contexto_auth) -> None:
    async with cliente_http() as c:
        primera = await c.post(
            "/auth/registro",
            json={
                "email": "doc1@taller.local",
                "nombre": "Doc1",
                "password": PASSWORD,
                "documento": "DOC-SHARED",
                "telefono": "123456",
            },
        )
        segunda = await c.post(
            "/auth/registro",
            json={
                "email": "doc2@taller.local",
                "nombre": "Doc2",
                "password": PASSWORD,
                "documento": "DOC-SHARED",
                "telefono": "123456",
            },
        )
    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.json()["codigo"] == "DOCUMENTO_DUPLICADO"

    count_u = await contexto_auth.scalar(select(func.count(Usuario.id)).where(Usuario.email.in_(["doc1@taller.local", "doc2@taller.local"])))
    assert count_u == 1


@pytest.mark.asyncio
async def test_registro_invalido_422(contexto_auth) -> None:
    total_antes = await contexto_auth.scalar(select(func.count(Usuario.id)))
    async with cliente_http() as c:
        r = await c.post(
            "/auth/registro",
            json={
                "email": "extra@taller.local",
                "nombre": "Extra",
                "password": PASSWORD,
                "documento": "DOC-X",
                "telefono": "123",
                "foo": "bar",
            },
        )
    assert r.status_code == 422
    assert r.json()["codigo"] == "ERROR_VALIDACION"
    total_despues = await contexto_auth.scalar(select(func.count(Usuario.id)))
    assert total_despues == total_antes


@pytest.mark.asyncio
async def test_registro_concurrencia_mismo_email() -> None:
    import uuid
    suf = uuid.uuid4().hex[:8]
    email = f"conc-{suf}@taller.local"
    payload = {
        "email": email,
        "nombre": "Conc",
        "password": PASSWORD,
        "documento": f"DOC-CONC-{suf}",
        "telefono": "123456",
    }
    payload2 = dict(payload, documento=f"DOC-CONC2-{suf}")

    async def do(p):
        async with cliente_http() as c:
            return await c.post("/auth/registro", json=p)

    r1, r2 = await asyncio.gather(do(payload), do(payload2))
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409], (r1.status_code, r1.text, r2.status_code, r2.text)

    # Limpieza para no contaminar la base real
    import os
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM asignacion_rol WHERE usuario_id IN (SELECT id FROM usuario WHERE email = :e)"), {"e": email})
        await conn.execute(text("DELETE FROM cliente WHERE usuario_id IN (SELECT id FROM usuario WHERE email = :e)"), {"e": email})
        await conn.execute(text("DELETE FROM evento_seguridad WHERE actor = :e"), {"e": email})
        await conn.execute(text("DELETE FROM usuario WHERE email = :e"), {"e": email})
    await engine.dispose()
