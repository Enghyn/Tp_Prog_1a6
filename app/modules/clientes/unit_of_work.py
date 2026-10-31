from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository, VehiculoRepository


class ClientesUnitOfWork(UnitOfWork):
    def __init__(self, session) -> None:
        super().__init__(session)
        self._clientes = None
        self._vehiculos = None

    @property
    def clientes(self) -> ClienteRepository:
        if self._clientes is None:
            self._clientes = ClienteRepository(self.session)
        return self._clientes

    @property
    def vehiculos(self) -> VehiculoRepository:
        if self._vehiculos is None:
            self._vehiculos = VehiculoRepository(self.session)
        return self._vehiculos