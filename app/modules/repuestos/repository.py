from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.repuestos.models import (
    HistorialPrecioRepuesto,
    MovimientoStock,
    Repuesto,
)


class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Repuesto)


class MovimientoStockRepository(BaseRepository[MovimientoStock]):
    """Append-only: los triggers de BD bloquean UPDATE/DELETE (RN-11)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MovimientoStock)

    async def update(self, entity: MovimientoStock) -> MovimientoStock:  # type: ignore[override]
        raise NotImplementedError("MovimientoStock es append-only (RN-11)")

    async def delete(self, entity: MovimientoStock) -> None:  # type: ignore[override]
        raise NotImplementedError("MovimientoStock es append-only (RN-11)")


class HistorialPrecioRepuestoRepository(BaseRepository[HistorialPrecioRepuesto]):
    """Append-only: los triggers de BD bloquean UPDATE/DELETE (RN-11)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialPrecioRepuesto)

    async def update(self, entity: HistorialPrecioRepuesto) -> HistorialPrecioRepuesto:  # type: ignore[override]
        raise NotImplementedError("HistorialPrecioRepuesto es append-only (RN-11)")

    async def delete(self, entity: HistorialPrecioRepuesto) -> None:  # type: ignore[override]
        raise NotImplementedError("HistorialPrecioRepuesto es append-only (RN-11)")
