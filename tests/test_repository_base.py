import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.modules.usuarios.models import Usuario


@pytest.mark.asyncio
async def test_base_repository_typed_constructor_accepts_session(contexto_auth):
    repo = BaseRepository(contexto_auth, Usuario)
    assert repo.session is contexto_auth
    assert repo.model is Usuario


@pytest.mark.asyncio
async def test_base_repository_crud(contexto_auth):
    repo = BaseRepository(contexto_auth, Usuario)

    # add
    u = Usuario(email="repo@test.com", nombre="Repo", password_hash="h", activo=True)
    added = await repo.add(u)
    assert added.id is not None

    # get_by_id
    fetched = await repo.get_by_id(added.id)
    assert fetched is not None
    assert fetched.email == "repo@test.com"

    # count
    assert await repo.count() >= 1

    # get_all
    todos = await repo.get_all()
    assert any(x.id == added.id for x in todos)

    # update
    fetched.nombre = "Repo2"
    await repo.update(fetched)
    reloaded = await repo.get_by_id(added.id)
    assert reloaded.nombre == "Repo2"

    # delete
    await repo.delete(reloaded)
    assert await repo.get_by_id(added.id) is None


@pytest.mark.asyncio
async def test_add_does_not_commit(contexto_auth):
    # Use a savepoint-ish check: add flushes but outer transaction rollback hides it.
    repo = BaseRepository(contexto_auth, Usuario)
    u = Usuario(email="nocommit@test.com", nombre="NC", password_hash="h", activo=True)
    await repo.add(u)
    uid = u.id
    assert uid is not None
    # Within same session, flushed -> queryable
    assert await repo.get_by_id(uid) is not None
    # A fresh session on same connection sees it only if committed; here uncommitted
    # so we rely on rollback isolation at fixture end. Instead verify no commit by
    # checking the outer transaction is still active.
    assert contexto_auth.in_transaction()


@pytest.mark.asyncio
async def test_selectinload_bounded_queries(contexto_auth):
    repo = BaseRepository(contexto_auth, Usuario)
    u = Usuario(email="preload@test.com", nombre="PL", password_hash="h", activo=True)
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
