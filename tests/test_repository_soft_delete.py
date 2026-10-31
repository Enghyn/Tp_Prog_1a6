import pytest

from app.core.repository import SoftDeleteRepository
from app.modules.repuestos.models import Repuesto


@pytest.mark.asyncio
async def test_soft_delete_repository(contexto_auth):
    repo = SoftDeleteRepository(contexto_auth, Repuesto)

    c = Repuesto(codigo="SOFT1", descripcion="Soft delete", precio=10, stock_actual=5, stock_minimo=1)
    await repo.add(c)
    await contexto_auth.flush()
    cid = c.id

    # default filters
    assert await repo.get_by_id(cid) is not None
    assert any(x.id == cid for x in await repo.get_all())

    # soft delete sets borrado_en
    await repo.soft_delete(c)
    await contexto_auth.flush()
    assert c.borrado_en is not None

    # excluded from default reads
    assert await repo.get_by_id(cid) is None
    assert not any(x.id == cid for x in await repo.get_all())

    # found via including_deleted
    incl = await repo.get_by_id_including_deleted(cid)
    assert incl is not None
    assert incl.id == cid
