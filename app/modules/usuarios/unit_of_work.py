"""Unit of Work for the usuarios module.

Exposes repositories as lazy properties over a shared session. Commit/rollback
are owned by the base UnitOfWork.__aexit__; repositories only flush.

Sub-UoW rule: only independent audit writes (intento_acceso) may use a separate
UoW/session. Domain writes MUST share the request UoW.
"""

from app.core.repository import BaseRepository
from app.core.unit_of_work import UnitOfWork
from app.modules.usuarios.models import Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad
from app.modules.usuarios.repository import (
    UsuarioRepository,
    AsignacionRolRepository,
    IntentoAccesoRepository,
    EventoSeguridadRepository,
)
from app.modules.clientes.repository import ClienteRepository


class UsuariosUnitOfWork(UnitOfWork):
    def __init__(self, session) -> None:
        super().__init__(session)
        self._usuarios = None
        self._asignaciones = None
        self._intentos = None
        self._eventos = None

    @property
    def usuarios(self) -> UsuarioRepository:
        if self._usuarios is None:
            self._usuarios = UsuarioRepository(self.session)
        return self._usuarios

    @property
    def asignaciones_rol(self) -> AsignacionRolRepository:
        if self._asignaciones is None:
            self._asignaciones = AsignacionRolRepository(self.session)
        return self._asignaciones

    @property
    def intentos_acceso(self) -> IntentoAccesoRepository:
        if self._intentos is None:
            self._intentos = IntentoAccesoRepository(self.session)
        return self._intentos

    @property
    def eventos_seguridad(self) -> EventoSeguridadRepository:
        if self._eventos is None:
            self._eventos = EventoSeguridadRepository(self.session)
        return self._eventos


class RegistroUnitOfWork(UnitOfWork):
    """UnitOfWork dedicado al auto-registro (C-17).

    Compone los repositorios de `usuarios` y `clientes` sobre una sola sesión,
    de modo que `Usuario` + `AsignacionRol(CLIENTE)` + `Cliente` se confirmen
    o reviertan en bloque (RN-02).
    """

    def __init__(self, session) -> None:
        super().__init__(session)
        self._usuarios = None
        self._asignaciones = None
        self._eventos = None
        self._clientes = None

    @property
    def usuarios(self) -> UsuarioRepository:
        if self._usuarios is None:
            self._usuarios = UsuarioRepository(self.session)
        return self._usuarios

    @property
    def asignaciones_rol(self) -> AsignacionRolRepository:
        if self._asignaciones is None:
            self._asignaciones = AsignacionRolRepository(self.session)
        return self._asignaciones

    @property
    def eventos_seguridad(self) -> EventoSeguridadRepository:
        if self._eventos is None:
            self._eventos = EventoSeguridadRepository(self.session)
        return self._eventos

    @property
    def clientes(self) -> ClienteRepository:
        if self._clientes is None:
            self._clientes = ClienteRepository(self.session)
        return self._clientes