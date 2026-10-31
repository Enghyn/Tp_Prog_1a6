from datetime import datetime, timezone
from typing import AsyncGenerator, Sequence
from fastapi import Request
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import session_maker
from app.core.repository import BaseRepository
from app.core.errors import NoAutenticadoError
from app.modules.usuarios.models import Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad


async def obtener_sesion_auditoria(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para inyectar una sesión independiente para la auditoría de seguridad (D3).
    Abre una sesión nueva y no forma parte del Unit of Work del request de dominio.
    """
    maker = getattr(request.app.state, "session_maker", None) or session_maker
    async with maker() as sesion:
        yield sesion


async def obtener_sesion_cambio_password(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de una sesión dedicada para el cambio de contraseña (D4).

    La sesión del request ya tiene una transacción autobegin abierta por
    `obtener_usuario_actual`, por lo que el service no puede hacer
    `async with sesion.begin()` sobre ella. Esta sesión no comparte identidad
    ni transacción con la del request.

    C-14: el límite transaccional lo administra el UnitOfWork.
    """
    maker = getattr(request.app.state, "session_maker", None) or session_maker
    async with maker() as sesion:
        yield sesion


async def obtener_sesion_admin_usuarios(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de una sesión dedicada para las escrituras de administración (D2).

    Gemela de `obtener_sesion_cambio_password`: la sesión del request ya tiene
    una transacción autobegin abierta por la autorización (`require_roles`), por
    lo que el service no puede abrir `async with sesion.begin()` sobre ella.

    C-14: el límite transaccional lo administra el UnitOfWork.
    """
    maker = getattr(request.app.state, "session_maker", None) or session_maker
    async with maker() as sesion:
        yield sesion


async def actualizar_password(
    sesion: AsyncSession,
    usuario_id: int,
    password_hash: str,
    cambiada_en: datetime,
) -> int:
    """
    Actualiza atómicamente hash, timestamp y bandera del usuario (D4, RN-07).

    Un único `UPDATE ... WHERE id = :id`; verifica `rowcount == 1` y lanza el
    `401` uniforme si la fila desapareció. No hace `commit()` ni cierra la
    sesión: el límite transaccional lo administra quien llama.
    """
    stmt = (
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(
            password_hash=password_hash,
            password_cambiada_en=cambiada_en,
            debe_cambiar_password=False,
        )
    )
    resultado = await sesion.execute(stmt)
    filas = resultado.rowcount
    if filas != 1:
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")
    await sesion.flush()
    return filas


async def registrar_intento(
    sesion: AsyncSession,
    email: str,
    ip: str,
    cuando: datetime,
    exito: bool,
) -> IntentoAcceso:
    """Registra una fila en intento_acceso."""
    if cuando.tzinfo is None:
        cuando = cuando.replace(tzinfo=timezone.utc)
    intento = IntentoAcceso(email=email, ip=ip, cuando=cuando, exito=exito)
    sesion.add(intento)
    return intento


async def registrar_evento(
    sesion: AsyncSession,
    actor: str,
    accion: str,
    cuando: datetime | None = None,
) -> EventoSeguridad:
    """Registra una fila en evento_seguridad."""
    instante = cuando or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    evento = EventoSeguridad(actor=actor, accion=accion, cuando=instante)
    sesion.add(evento)
    return evento


async def buscar_usuario_por_email(sesion: AsyncSession, email: str) -> Usuario | None:
    """
    Busca un usuario por su email cargando sus asignaciones de rol con selectinload (regla dura #3).
    """
    email_normalizado = email.strip().lower()
    stmt = (
        select(Usuario)
        .options(selectinload(Usuario.asignaciones))
        .where(func.lower(Usuario.email) == email_normalizado)
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalars().first()


async def obtener_roles_vigentes_por_usuario(
    sesion: AsyncSession,
    usuario_id: int,
) -> list[str]:
    """
    Devuelve los roles vigentes del usuario leídos de `asignacion_rol` (RN-04, D2).

    `ahora` se calcula en Python una sola vez por llamada y se envía como
    parámetro: dentro de una transacción externa el `now()` de PostgreSQL
    devolvería el inicio de la transacción y congelaría los tests de vencimiento.
    La comparación es estricta (`vence_en > ahora`): una asignación que vence
    exactamente en el instante evaluado ya no autoriza.
    """
    ahora = datetime.now(timezone.utc)
    stmt = (
        select(AsignacionRol.rol)
        .where(
            AsignacionRol.usuario_id == usuario_id,
            AsignacionRol.revocada_en.is_(None),
            or_(AsignacionRol.vence_en.is_(None), AsignacionRol.vence_en > ahora),
        )
        .distinct()
        .order_by(AsignacionRol.rol)
    )
    resultado = await sesion.execute(stmt)
    return list(resultado.scalars().all())


async def crear_usuario(
    sesion: AsyncSession,
    email: str,
    nombre: str,
    password_hash: str,
) -> Usuario:
    """
    Inserta un usuario activo con contraseña provisoria (D3).

    El email llega ya normalizado. Sólo hace `flush()`: el límite transaccional
    lo administra el service con `async with sesion.begin()` (regla dura #2).
    """
    usuario = Usuario(
        email=email,
        nombre=nombre,
        password_hash=password_hash,
        activo=True,
        debe_cambiar_password=True,
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


def condiciones_vigencia(ahora: datetime) -> list:
    """
    Predicado SQL único de vigencia (RN-04, D5).

    `revocada_en IS NULL AND (vence_en IS NULL OR vence_en > :ahora)`. Se
    reutiliza en la lectura de roles, en el conteo de administradores y en la
    búsqueda de una asignación abierta, sin duplicar SQL (task 6.9).
    """
    return [
        AsignacionRol.revocada_en.is_(None),
        or_(AsignacionRol.vence_en.is_(None), AsignacionRol.vence_en > ahora),
    ]


async def listar_asignaciones(
    sesion: AsyncSession,
    usuario_id: int,
) -> Sequence[AsignacionRol]:
    """
    Devuelve todas las asignaciones del usuario, vigentes y revocadas (D5).

    Consulta plana sobre `asignacion_rol`: no navega `AsignacionRol.usuario` ni
    `otorgado_por_usuario`, que están en `lazy="raise"` (regla dura #3).
    """
    stmt = (
        select(AsignacionRol)
        .where(AsignacionRol.usuario_id == usuario_id)
        .order_by(AsignacionRol.desde.desc(), AsignacionRol.id.desc())
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalars().all()


async def buscar_asignacion_abierta(
    sesion: AsyncSession,
    usuario_id: int,
    rol: str,
) -> AsignacionRol | None:
    """
    Devuelve la única fila abierta (`revocada_en IS NULL`) del par usuario/rol.

    El índice parcial `uq_asignacion_rol_abierta` garantiza que no haya más de
    una. Una fila vencida sigue siendo "abierta" para el índice, por eso el
    service la cierra antes de insertar (D6).
    """
    stmt = (
        select(AsignacionRol)
        .where(
            AsignacionRol.usuario_id == usuario_id,
            AsignacionRol.rol == rol,
            AsignacionRol.revocada_en.is_(None),
        )
        .order_by(AsignacionRol.desde.desc(), AsignacionRol.id.desc())
        .limit(1)
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalars().first()


async def cerrar_asignacion(
    sesion: AsyncSession,
    asignacion_id: int,
    revocada_en: datetime,
) -> int:
    """Marca `revocada_en` sobre la fila indicada sin borrarla (RN-05, D7)."""
    stmt = (
        update(AsignacionRol)
        .where(AsignacionRol.id == asignacion_id)
        .values(revocada_en=revocada_en)
    )
    resultado = await sesion.execute(stmt)
    await sesion.flush()
    return resultado.rowcount


async def crear_asignacion(
    sesion: AsyncSession,
    *,
    usuario_id: int,
    rol: str,
    desde: datetime,
    vence_en: datetime | None,
    otorgada_por: int | None,
) -> AsignacionRol:
    """Inserta una asignación abierta. Sólo hace `flush()` (regla dura #2)."""
    asignacion = AsignacionRol(
        usuario_id=usuario_id,
        rol=rol,
        desde=desde,
        vence_en=vence_en,
        revocada_en=None,
        otorgada_por=otorgada_por,
    )
    sesion.add(asignacion)
    await sesion.flush()
    return asignacion


async def contar_admins_vigentes(
    sesion: AsyncSession,
    ahora: datetime,
) -> int:
    """
    Cuenta las asignaciones `ADMIN` vigentes del sistema (RN-05).

    Usa el mismo predicado que `obtener_roles_vigentes_por_usuario` para que la
    decisión y la autorización nunca discrepen (task 6.9).
    """
    stmt = select(func.count(AsignacionRol.id)).where(
        AsignacionRol.rol == "ADMIN",
        *condiciones_vigencia(ahora),
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalar_one() or 0


async def contar_intentos_fallidos(
    sesion: AsyncSession,
    email: str,
    ip: str,
    desde: datetime,
) -> int:
    """
    Cuenta los intentos fallidos para el par (email, ip) ocurridos desde 'desde' (RN-08, D4).
    """
    email_normalizado = email.strip().lower()
    stmt = (
        select(func.count(IntentoAcceso.id))
        .where(
            func.lower(IntentoAcceso.email) == email_normalizado,
            IntentoAcceso.ip == ip,
            IntentoAcceso.cuando >= desde,
            IntentoAcceso.exito == False,  # noqa: E712
        )
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalar_one() or 0


async def obtener_ultimos_fallos_ventana(
    sesion: AsyncSession,
    email: str,
    ip: str,
    desde: datetime,
    limite: int = 5,
) -> Sequence[IntentoAcceso]:
    """
    Obtiene los intentos fallidos de la ventana ordenados cronológicamente ascendente
    para el cálculo preciso de Retry-After (D5).
    """
    email_normalizado = email.strip().lower()
    stmt = (
        select(IntentoAcceso)
        .where(
            func.lower(IntentoAcceso.email) == email_normalizado,
            IntentoAcceso.ip == ip,
            IntentoAcceso.cuando >= desde,
            IntentoAcceso.exito == False,  # noqa: E712
        )
        .order_by(IntentoAcceso.cuando.asc())
        .limit(limite)
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalars().all()


# --- eventos de auditoría (C-12) ---


async def contar_eventos(
    sesion: AsyncSession,
    *,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    actor: str | None = None,
) -> int:
    stmt = select(func.count(EventoSeguridad.id))
    if actor is not None:
        stmt = stmt.where(EventoSeguridad.actor == actor)
    if desde is not None:
        stmt = stmt.where(EventoSeguridad.cuando >= desde)
    if hasta is not None:
        stmt = stmt.where(EventoSeguridad.cuando <= hasta)
    resultado = await sesion.execute(stmt)
    return resultado.scalar_one() or 0


async def listar_eventos(
    sesion: AsyncSession,
    *,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    actor: str | None = None,
    pagina: int = 1,
    tamanio: int = 10,
) -> Sequence[EventoSeguridad]:
    stmt = select(EventoSeguridad)
    if actor is not None:
        stmt = stmt.where(EventoSeguridad.actor == actor)
    if desde is not None:
        stmt = stmt.where(EventoSeguridad.cuando >= desde)
    if hasta is not None:
        stmt = stmt.where(EventoSeguridad.cuando <= hasta)
    stmt = (
        stmt.order_by(EventoSeguridad.cuando.desc(), EventoSeguridad.id.desc())
        .offset((pagina - 1) * tamanio)
        .limit(tamanio)
    )
    resultado = await sesion.execute(stmt)
    return resultado.scalars().all()


# --- Pilot repository classes (C-13) ---

class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Usuario)

class AsignacionRolRepository(BaseRepository[AsignacionRol]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AsignacionRol)

class IntentoAccesoRepository(BaseRepository[IntentoAcceso]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IntentoAcceso)

class EventoSeguridadRepository(BaseRepository[EventoSeguridad]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EventoSeguridad)
