from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence, Any
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configuracion import configuracion
from app.core.errors import (
    ConflictoError,
    DemasiadasPeticionesError,
    NoAutenticadoError,
    NoEncontradoError,
)
from app.core.seguridad import (
    crear_token_acceso,
    verify_password_o_dummy,
    generar_hash_ficticio,
    hash_password,
    verify_password_async,
)
from app.modules.usuarios.repository import (
    registrar_intento,
    registrar_evento,
    buscar_asignacion_abierta,
    buscar_usuario_por_email,
    cerrar_asignacion,
    contar_admins_vigentes,
    contar_intentos_fallidos,
    obtener_ultimos_fallos_ventana,
    actualizar_password,
    crear_asignacion,
    crear_usuario,
    listar_asignaciones,
)
from app.modules.usuarios.models import IntentoAcceso, AsignacionRol, Usuario
from app.modules.usuarios.schemas import (
    AsignacionRolPublica,
    HistorialRoles,
    RespuestaCambioPassword,
    RespuestaSesion,
    SolicitudAltaUsuario,
    SolicitudAsignacionRol,
    UsuarioCreado,
    UsuarioPublico,
    TokenInfo,
    normalizar_email_valor,
)


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


def credenciales_invalidas() -> NoAutenticadoError:
    """
    Construye el `401` uniforme compartido por login y cambio de contraseña (D9).

    No distingue causas: ni la existencia del usuario ni cuál de las dos
    contraseñas falló se revelan en el cuerpo.
    """
    return NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")


def _ahora() -> datetime:
    """
    Reloj inyectable del módulo (D3).

    Se captura después del hash y antes del UPDATE, de modo que cualquier token
    emitido mientras se calculaba la contraseña nueva quede invalidado (RN-07).
    """
    return datetime.now(timezone.utc)


async def cambiar_password(
    usuario: Usuario,
    password_actual: str,
    password_nueva: str,
    ip: str,
    sesion_cambio: AsyncSession,
    sesion_auditoria: AsyncSession,
    app_state: Any = None,
) -> RespuestaCambioPassword:
    """
    Cambio de contraseña autenticado (D3): verificar → hashear → persistir → auditar.

    La sesión `sesion_cambio` es dedicada (D4) porque la del request ya tiene una
    transacción autobegin. `actualizar_password` no commitea: el bloque `begin()`
    es el límite transaccional local hasta que C-14 introduzca el UnitOfWork.
    """
    if not await verify_password_async(
        password_actual, usuario.password_hash, app_state
    ):
        raise credenciales_invalidas()

    nuevo_hash = await hash_password(password_nueva, app_state)
    ahora = _ahora()

    # TODO(C-14): reemplazar este límite transaccional local por UnitOfWork.__aexit__.
    async with sesion_cambio.begin():
        await actualizar_password(
            sesion_cambio,
            usuario_id=usuario.id,
            password_hash=nuevo_hash,
            cambiada_en=ahora,
        )

    await auditar_acceso(
        sesion_auditoria,
        RegistroAcceso(
            email=usuario.email,
            ip=ip,
            actor=usuario.email,
            accion="PASSWORD_CAMBIADA",
            exito=None,
            cuando=ahora,
        ),
    )

    return RespuestaCambioPassword()


async def _auditar_operacion(
    sesion_auditoria: AsyncSession,
    *,
    email: str,
    ip: str,
    actor: str,
    accion: str,
    cuando: datetime,
) -> None:
    """
    Helper único de auditoría de las operaciones administrativas (D9, task 7.5).

    `exito=None` evita escribir en `intento_acceso`: estos eventos no son
    intentos de login.
    """
    await auditar_acceso(
        sesion_auditoria,
        RegistroAcceso(
            email=email,
            ip=ip,
            actor=actor,
            accion=accion,
            exito=None,
            cuando=cuando,
        ),
    )


async def dar_de_alta_usuario(
    *,
    solicitud: SolicitudAltaUsuario,
    admin: Usuario,
    ip: str,
    sesion_admin: AsyncSession,
    sesion_auditoria: AsyncSession,
    app_state: Any = None,
) -> UsuarioCreado:
    """
    Alta de personal (D3, D4): pre-chequeo de email → hash → escritura → auditoría.

    El hash bcrypt corre fuera del bloque transaccional para no retener la
    transacción durante el trabajo de CPU. La auditoría va después del commit de
    dominio, en su propia transacción (D2).
    """
    email = normalizar_email_valor(solicitud.email)
    password_hash = await hash_password(solicitud.password, app_state)
    ahora = _ahora()

    # TODO(C-14): reemplazar este límite transaccional local por UnitOfWork.__aexit__.
    async with sesion_admin.begin():
        if await buscar_usuario_por_email(sesion_admin, email) is not None:
            raise ConflictoError("El email ya está registrado", "EMAIL_DUPLICADO")
        usuario = await crear_usuario(
            sesion_admin,
            email=email,
            nombre=solicitud.nombre,
            password_hash=password_hash,
        )

    await _auditar_operacion(
        sesion_auditoria,
        email=email,
        ip=ip,
        actor=admin.email,
        accion="USUARIO_CREADO",
        cuando=ahora,
    )

    return UsuarioCreado(
        id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        activo=usuario.activo,
        debe_cambiar_password=usuario.debe_cambiar_password,
    )


def _publicar_asignacion(
    asignacion: AsignacionRol,
    ahora: datetime,
) -> AsignacionRolPublica:
    """Proyección única de `AsignacionRol` a la vista pública (D5, task 5.9)."""
    return AsignacionRolPublica(
        id=asignacion.id,
        rol=asignacion.rol,
        desde=asignacion.desde,
        vence_en=asignacion.vence_en,
        revocada_en=asignacion.revocada_en,
        otorgada_por=asignacion.otorgada_por,
        vigente=es_asignacion_vigente(asignacion, ahora),
    )


async def asignar_rol(
    *,
    usuario_id: int,
    solicitud: SolicitudAsignacionRol,
    admin: Usuario,
    ip: str,
    sesion_admin: AsyncSession,
    sesion_auditoria: AsyncSession,
) -> AsignacionRolPublica:
    """
    Asignación de rol con vencimiento opcional (D6).

    Una única transacción de dominio: verificación del usuario, cierre de la
    asignación vencida (el índice parcial no la excluye), `INSERT` de la fila
    nueva y `flush()`. La auditoría va después del commit (D2, D9).
    """
    ahora = _ahora()

    # TODO(C-14): reemplazar este límite transaccional local por UnitOfWork.__aexit__.
    async with sesion_admin.begin():
        usuario = await sesion_admin.get(Usuario, usuario_id)
        if usuario is None:
            raise NoEncontradoError("Usuario no encontrado", "USUARIO_NO_ENCONTRADO")

        abierta = await buscar_asignacion_abierta(
            sesion_admin, usuario_id, solicitud.rol
        )
        if abierta is not None:
            if es_asignacion_vigente(abierta, ahora):
                raise ConflictoError(
                    "El usuario ya tiene ese rol vigente", "ROL_YA_ASIGNADO"
                )
            await cerrar_asignacion(sesion_admin, abierta.id, ahora)

        asignacion = await crear_asignacion(
            sesion_admin,
            usuario_id=usuario_id,
            rol=solicitud.rol,
            desde=ahora,
            vence_en=solicitud.vence_en,
            otorgada_por=admin.id,
        )

    await _auditar_operacion(
        sesion_auditoria,
        email=usuario.email,
        ip=ip,
        actor=admin.email,
        accion="ROL_ASIGNADO",
        cuando=ahora,
    )

    return _publicar_asignacion(asignacion, ahora)


async def obtener_historial_roles(
    sesion: AsyncSession,
    usuario_id: int,
) -> HistorialRoles:
    """
    Historial completo de asignaciones de un usuario (D5).

    `vigente` se calcula con un único `ahora` por request; `404` si el usuario
    no existe (no se confunde "sin roles" con "usuario inexistente").
    """
    usuario = await sesion.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontradoError("Usuario no encontrado", "USUARIO_NO_ENCONTRADO")

    ahora = _ahora()
    asignaciones = await listar_asignaciones(sesion, usuario_id)

    return HistorialRoles(
        usuario_id=usuario_id,
        asignaciones=[
            _publicar_asignacion(asignacion, ahora)
            for asignacion in asignaciones
        ],
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


def es_asignacion_vigente(asignacion: AsignacionRol, ahora: datetime) -> bool:
    """
    Predicado único de vigencia de una asignación (RN-04, D5).

    `revocada_en IS NULL` y (`vence_en IS NULL` o `vence_en > ahora`). La
    comparación es estricta: una asignación que vence exactamente en el
    instante evaluado ya no autoriza. Las fechas ingenuas se interpretan
    como UTC, igual que la consulta SQL del repositorio.
    """
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    if asignacion.revocada_en is not None:
        return False
    if asignacion.vence_en is None:
        return True
    vence = asignacion.vence_en
    if vence.tzinfo is None:
        vence = vence.replace(tzinfo=timezone.utc)
    return vence > ahora


def obtener_roles_vigentes(
    asignaciones: Sequence[AsignacionRol],
    ahora: datetime | None = None,
) -> list[str]:
    """
    Filtra los roles vigentes en el instante dado (RN-04, D11).

    Delega el cálculo en `es_asignacion_vigente` para no duplicar la regla.
    """
    instante = ahora or datetime.now(timezone.utc)
    return [
        asignacion.rol
        for asignacion in asignaciones
        if es_asignacion_vigente(asignacion, instante)
    ]


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
        raise credenciales_invalidas()

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
