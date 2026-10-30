import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")


@pytest.mark.asyncio
async def test_usuario_email_unico(test_db_session):
    from app.modules.usuarios.models import Usuario

    session = test_db_session
    u1 = Usuario(
        email="test@example.com",
        nombre="Test",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u1)
    await session.flush()

    u2 = Usuario(
        email="test@example.com",
        nombre="Test2",
        password_hash="hash2",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_asignacion_rol_check_invalido(test_db_session):
    from app.modules.usuarios.models import AsignacionRol, Usuario
    from datetime import datetime, timezone

    session = test_db_session
    u = Usuario(
        email="rol@example.com",
        nombre="Rol",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u)
    await session.flush()

    a = AsignacionRol(usuario_id=u.id, rol="INVALIDO", desde=datetime.now(timezone.utc))
    session.add(a)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_asignacion_rol_unica_abierta_reasignacion(test_db_session):
    from app.modules.usuarios.models import AsignacionRol, Usuario
    from datetime import datetime, timezone

    session = test_db_session
    u = Usuario(
        email="rol2@example.com",
        nombre="Rol2",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u)
    await session.flush()

    a1 = AsignacionRol(usuario_id=u.id, rol="ADMIN", desde=datetime.now(timezone.utc))
    session.add(a1)
    await session.flush()

    a2 = AsignacionRol(usuario_id=u.id, rol="ADMIN", desde=datetime.now(timezone.utc))
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(a2)
            await session.flush()

    # revoke first and assign again
    a1.revocada_en = datetime.now(timezone.utc)
    await session.flush()

    a3 = AsignacionRol(usuario_id=u.id, rol="ADMIN", desde=datetime.now(timezone.utc))
    session.add(a3)
    await session.flush()


@pytest.mark.asyncio
async def test_lazy_raise_on_relationships(test_db_session):
    from app.modules.usuarios.models import AsignacionRol, Usuario
    from datetime import datetime, timezone
    from sqlalchemy.orm import object_session

    session = test_db_session
    u = Usuario(
        email="lazy@example.com",
        nombre="Lazy",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u)
    await session.flush()
    a = AsignacionRol(usuario_id=u.id, rol="CLIENTE", desde=datetime.now(timezone.utc))
    session.add(a)
    await session.flush()
    await session.refresh(u)

    with pytest.raises(Exception):
        _ = u.asignaciones


@pytest.mark.asyncio
async def test_intento_acceso_y_evento_seguridad(test_db_session):
    from app.modules.usuarios.models import IntentoAcceso, EventoSeguridad
    from datetime import datetime, timezone

    session = test_db_session
    ia = IntentoAcceso(cuando=datetime.now(timezone.utc), email="x@y.com", ip="1.2.3.4", exito=False)
    session.add(ia)
    await session.flush()

    es = EventoSeguridad(actor="x@y.com", accion="LOGIN_FALLIDO")
    session.add(es)
    await session.flush()
    assert es.cuando is not None
