from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence, Any
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configuracion import configuracion
from app.core.errors import NoAutenticadoError, DemasiadasPeticionesError
from app.core.seguridad import (
    crear_token_acceso,
    verify_password_o_dummy,
    generar_hash_ficticio,
)
from app.modules.usuarios.repository import (
    registrar_intento,
    registrar_evento,
    buscar_usuario_por_email,
    contar_intentos_fallidos,
    obtener_ultimos_fallos_ventana,
)
from app.modules.usuarios.models import IntentoAcceso, AsignacionRol, Usuario
from app.modules.usuarios.schemas import RespuestaSesion, UsuarioPublico, TokenInfo


@dataclass(frozen=True)
class RegistroAcceso:
    """
    Contrato mínimo para la auditoría de acceso (Task 4.6, D13).
    """
    email: str
    ip: str
    actor: str
    accion: str
    exito: bool | None = None
    cuando: datetime | None = None


async def auditar_acceso(
    sesion_auditoria: AsyncSession,
    registro: RegistroAcceso,
) -> None:
    """
    Escribe el intento de acceso y el evento de seguridad en una transacción independiente.
    Si la auditoría falla, la excepción se propaga (D13, Prioridad integridad RN-08).
    """
    instante = registro.cuando or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)

    async with sesion_auditoria.begin():
        if registro.exito is not None:
            await registrar_intento(
                sesion_auditoria,
                email=registro.email,
                ip=registro.ip,
                cuando=instante,
                exito=registro.exito,
            )
        await registrar_evento(
            sesion_auditoria,
            actor=registro.actor,
            accion=registro.accion,
            cuando=instante,
        )


def calcular_retry_after(
    fallos_ventana: Sequence[IntentoAcceso],
    ahora: datetime,
    ventana_seg: int,
) -> int:
    """
    Calcula los segundos de Retry-After según D5:
    liberacion = fallo_mas_antiguo.cuando + ventana_seg
    retry_after = max(1, min(ventana_seg, ceil(liberacion - ahora)))
    """
    if not fallos_ventana:
        return 1
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)

    fallo_base = fallos_ventana[0]
    cuando_fallo = fallo_base.cuando
    if cuando_fallo.tzinfo is None:
        cuando_fallo = cuando_fallo.replace(tzinfo=timezone.utc)

    segundos_restantes = (cuando_fallo.timestamp() + ventana_seg) - ahora.timestamp()
    retry_after = math.ceil(segundos_restantes)
    if retry_after < 1:
        return 1
    if retry_after > ventana_seg:
        return ventana_seg
    return retry_after


def obtener_roles_vigentes(
    asignaciones: Sequence[AsignacionRol],
    ahora: datetime | None = None,
) -> list[str]:
    """
    Filtra los roles vigentes en el instante dado (RN-04, D11):
    revocada_en IS NULL y (vence_en IS NULL o vence_en > ahora).
    """
    instante = ahora or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)

    roles = []
    for asig in asignaciones:
        if asig.revocada_en is not None:
            continue
        if asig.vence_en is not None:
            vence = asig.vence_en
            if vence.tzinfo is None:
                vence = vence.replace(tzinfo=timezone.utc)
            if vence <= instante:
                continue
        roles.append(asig.rol)
    return roles


async def iniciar_sesion(
    email: str,
    password: str,
    ip: str,
    sesion: AsyncSession,
    sesion_auditoria: AsyncSession,
    app_state: Any = None,
) -> tuple[RespuestaSesion, str]:
    """
    Orquestación del flujo de inicio de sesión (D4):
    1. Verificación del rate limit por (email, ip) en la ventana configurada.
       Si fallos >= login_max_intentos -> LOGIN_BLOQUEADO y 429 con Retry-After (sin tocar bcrypt).
    2. Búsqueda de usuario y verificación bcrypt uniforme (con hash ficticio si no existe).
    3. Si credenciales inválidas o usuario inactivo -> LOGIN_FALLIDO y 401 uniforme.
    4. Si válidas -> LOGIN_OK, emisión de token JWT y RespuestaSesion.
    """
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(seconds=configuracion.login_ventana_seg)

    # 1. Control de intentos fallidos (RN-08)
    fallos = await contar_intentos_fallidos(sesion, email=email, ip=ip, desde=desde)
    if fallos >= configuracion.login_max_intentos:
        ultimos = await obtener_ultimos_fallos_ventana(
            sesion,
            email=email,
            ip=ip,
            desde=desde,
            limite=configuracion.login_max_intentos,
        )
        retry_after = calcular_retry_after(ultimos, ahora, configuracion.login_ventana_seg)
        await auditar_acceso(
            sesion_auditoria,
            RegistroAcceso(
                email=email,
                ip=ip,
                actor=email,
                accion="LOGIN_BLOQUEADO",
                exito=None,
                cuando=ahora,
            ),
        )
        raise DemasiadasPeticionesError(
            "Demasiadas peticiones. Intente más tarde.",
            "DEMASIADAS_PETICIONES",
            reintentar_despues=retry_after,
        )

    # 2. Búsqueda y verificación con protección de enumeración (RN-09)
    usuario = await buscar_usuario_por_email(sesion, email)
    hash_real = usuario.password_hash if usuario else None
    hash_ficticio = getattr(app_state, "hash_ficticio", None)
    if not hash_ficticio:
        hash_ficticio = generar_hash_ficticio()

    ok = await verify_password_o_dummy(password, hash_real, hash_ficticio, app_state)

    # 3. Validación de credenciales y estado activo
    if (not ok) or (usuario is None) or (not usuario.activo):
        await auditar_acceso(
            sesion_auditoria,
            RegistroAcceso(
                email=email,
                ip=ip,
                actor=email,
                accion="LOGIN_FALLIDO",
                exito=False,
                cuando=ahora,
            ),
        )
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")

    # 4. Éxito: emisión y auditoría independiente
    roles_vigentes = obtener_roles_vigentes(usuario.asignaciones, ahora)
    token = crear_token_acceso(usuario_id=usuario.id, roles=roles_vigentes, iat=ahora)

    await auditar_acceso(
        sesion_auditoria,
        RegistroAcceso(
            email=usuario.email,
            ip=ip,
            actor=usuario.email,
            accion="LOGIN_OK",
            exito=True,
            cuando=ahora,
        ),
    )

    exp = int((ahora + timedelta(minutes=configuracion.access_token_ttl_min)).timestamp())
    respuesta = RespuestaSesion(
        usuario=UsuarioPublico(
            id=usuario.id,
            email=usuario.email,
            nombre=usuario.nombre,
            debe_cambiar_password=usuario.debe_cambiar_password,
        ),
        roles=roles_vigentes,
        token=TokenInfo(
            iat=ahora.isoformat(),
            exp=exp,
        ),
    )
    return respuesta, token
