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