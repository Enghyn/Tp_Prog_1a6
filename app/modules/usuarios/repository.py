from datetime import datetime, timezone
from typing import AsyncGenerator, Sequence
from fastapi import Request
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import session_maker
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

    TODO(C-14): reemplazar este límite transaccional local por el UnitOfWork.
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
