import pytest
from sqlalchemy import event

from app.modules.usuarios.repository import (
    UsuarioRepository,
    AsignacionRolRepository,
    IntentoAccesoRepository,
    EventoSeguridadRepository,
)


@pytest.mark.asyncio
async def test_typed_constructors(contexto_auth):
    for cls in (UsuarioRepository, AsignacionRolRepository, IntentoAccesoRepository, EventoSeguridadRepository):
        repo = cls(contexto_auth)
        assert repo.session is contexto_auth


@pytest.mark.asyncio
async def test_usuario_repository_crud(contexto_auth):
    repo = UsuarioRepository(contexto_auth)
    u = (await repo.add(__import__("app.modules.usuarios.models", fromlist=["Usuario"]).Usuario(
        email="pilot@test.com", nombre="Pilot", password_hash="h", activo=True)))
    assert u.id is not None
    assert (await repo.get_by_id(u.id)).email == "pilot@test.com"
    assert await repo.count() >= 1
    assert any(x.id == u.id for x in await repo.get_all())
    u.nombre = "Pilot2"
    await repo.update(u)
    assert (await repo.get_by_id(u.id)).nombre == "Pilot2"
    await repo.delete(u)
    assert await repo.get_by_id(u.id) is None


@pytest.mark.asyncio
async def test_pilot_precarga_no_nplus1(contexto_auth):
    from app.modules.usuarios.models import Usuario
    repo = UsuarioRepository(contexto_auth)
    u = Usuario(email="pre2@test.com", nombre="P", password_hash="h", activo=True)
    await repo.add(u)
    await contexto_auth.flush()

    sentencias = []

    def registrar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            sentencias.append(statement)

    conexion = contexto_auth.bind
    objetivo = getattr(conexion, "sync_engine", None) or conexion.sync_connection
    event.listen(objetivo, "before_cursor_execute", registrar)
    try:
        fetched = await repo.get_by_id(u.id)
        assert fetched is not None
        assert len(sentencias) <= 1
    finally:
        event.remove(objetivo, "before_cursor_execute", registrar)
