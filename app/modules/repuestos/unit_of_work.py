from app.core.unit_of_work import UnitOfWork
from app.modules.repuestos.repository import (
    HistorialPrecioRepuestoRepository,
    MovimientoStockRepository,
    RepuestoRepository,
)


class RepuestosUnitOfWork(UnitOfWork):
    def __init__(self, session) -> None:
        super().__init__(session)
        self._repuestos = None
        self._movimientos = None
        self._precios = None

    @property
    def repuestos(self) -> RepuestoRepository:
        if self._repuestos is None:
            self._repuestos = RepuestoRepository(self.session)
        return self._repuestos

    @property
    def movimientos(self) -> MovimientoStockRepository:
        if self._movimientos is None:
            self._movimientos = MovimientoStockRepository(self.session)
        return self._movimientos

    @property
    def precios(self) -> HistorialPrecioRepuestoRepository:
        if self._precios is None:
            self._precios = HistorialPrecioRepuestoRepository(self.session)
        return self._precios
