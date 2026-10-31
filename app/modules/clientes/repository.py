from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.models import Cliente, Vehiculo


async def es_duenio_de_vehiculo(
    sesion: AsyncSession,
    usuario_id: int,
    vehiculo_id: int,
) -> bool:
    stmt = select(
        exists(
            select(Vehiculo.id)
            .join(Cliente, Cliente.id == Vehiculo.cliente_id)
            .where(
                Vehiculo.id == vehiculo_id,
                Cliente.usuario_id == usuario_id,
            )
        )
    )
    resultado = await sesion.execute(stmt)
    return bool(resultado.scalar())


class ClienteRepository(BaseRepository[Cliente]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Cliente)


class VehiculoRepository(SoftDeleteRepository[Vehiculo]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Vehiculo)