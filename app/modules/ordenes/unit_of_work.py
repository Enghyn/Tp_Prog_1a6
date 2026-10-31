from app.core.unit_of_work import UnitOfWork
from app.modules.ordenes.repository import (
    EstadoOrdenRepository,
    HistorialEstadoOrdenRepository,
    ItemOrdenRepository,
    OrdenRepository,
)


class OrdenesUnitOfWork(UnitOfWork):
    def __init__(self, session) -> None:
        super().__init__(session)
        self._ordenes = None
        self._items = None
        self._estados = None
        self._historial = None

    @property
    def ordenes(self) -> OrdenRepository:
        if self._ordenes is None:
            self._ordenes = OrdenRepository(self.session)
        return self._ordenes

    @property
    def items(self) -> ItemOrdenRepository:
        if self._items is None:
            self._items = ItemOrdenRepository(self.session)
        return self._items

    @property
    def estados(self) -> EstadoOrdenRepository:
        if self._estados is None:
            self._estados = EstadoOrdenRepository(self.session)
        return self._estados

    @property
    def historial(self) -> HistorialEstadoOrdenRepository:
        if self._historial is None:
            self._historial = HistorialEstadoOrdenRepository(self.session)
        return self._historial