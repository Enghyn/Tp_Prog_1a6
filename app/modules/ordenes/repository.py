from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)


async def es_duenio_de_orden(
    sesion: AsyncSession,
    usuario_id: int,
    orden_id: int,
) -> bool:
    stmt = select(
        exists(
            select(OrdenTrabajo.id)
            .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
            .join(Cliente, Cliente.id == Vehiculo.cliente_id)
            .where(
                OrdenTrabajo.id == orden_id,
                Cliente.usuario_id == usuario_id,
            )
        )
    )
    resultado = await sesion.execute(stmt)
    return bool(resultado.scalar())


class OrdenRepository(BaseRepository[OrdenTrabajo]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrdenTrabajo)

    def _loads(self):
        return (
            selectinload(OrdenTrabajo.vehiculo),
            selectinload(OrdenTrabajo.items).selectinload(ItemOrden.repuesto),
            selectinload(OrdenTrabajo.mecanico),
        )

    async def get_by_id(self, entity_id: int) -> OrdenTrabajo | None:
        stmt = (
            select(OrdenTrabajo)
            .options(*self._loads())
            .where(OrdenTrabajo.id == entity_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self, *, limit: int = 100, offset: int = 0, estado: str | None = None
    ):
        stmt = select(OrdenTrabajo).options(*self._loads())
        if estado is not None:
            stmt = stmt.where(OrdenTrabajo.estado == estado)
        stmt = stmt.order_by(OrdenTrabajo.id).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, *, estado: str | None = None) -> int:
        stmt = select(func.count()).select_from(OrdenTrabajo)
        if estado is not None:
            stmt = stmt.where(OrdenTrabajo.estado == estado)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0


class ItemOrdenRepository(BaseRepository[ItemOrden]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ItemOrden)


class EstadoOrdenRepository(BaseRepository[EstadoOrden]):
    """Catálogo de solo lectura: update/delete no permitidos."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EstadoOrden)

    async def get_all(self, *, limit: int = 100, offset: int = 0):
        stmt = (
            select(EstadoOrden)
            .order_by(EstadoOrden.posicion.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, entity: EstadoOrden) -> EstadoOrden:  # type: ignore[override]
        raise NotImplementedError("EstadoOrden es catálogo de solo lectura")

    async def delete(self, entity: EstadoOrden) -> None:  # type: ignore[override]
        raise NotImplementedError("EstadoOrden es catálogo de solo lectura")


class HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden]):
    """Append-only: update/delete bloqueados por trigger y por repositorio (RN-15)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialEstadoOrden)

    async def update(self, entity: HistorialEstadoOrden) -> HistorialEstadoOrden:  # type: ignore[override]
        raise NotImplementedError("HistorialEstadoOrden es append-only (RN-15)")

    async def delete(self, entity: HistorialEstadoOrden) -> None:  # type: ignore[override]
        raise NotImplementedError("HistorialEstadoOrden es append-only (RN-15)")