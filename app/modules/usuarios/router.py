from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import (
    SesionActual,
    get_roles_vigentes,
    obtener_usuario_actual,
    require_roles,
)
from app.core.seguridad import (
    construir_cookie_sesion,
    construir_cookie_borrado,
    decodificar_token_acceso,
)
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import (
    obtener_sesion_admin_usuarios,
    obtener_sesion_auditoria,
    obtener_sesion_cambio_password,
)
from app.modules.usuarios.schemas import (
    AsignacionRolPublica,
    HistorialRoles,
    SolicitudLogin,
    RespuestaSesion,
    RespuestaLogout,
    SolicitudAltaUsuario,
    SolicitudAsignacionRol,
    SolicitudRegistro,
    UsuarioCreado,
    UsuarioRegistrado,
    UsuarioPublico,
    TokenInfo,
    SolicitudCambioPassword,
    RespuestaCambioPassword,
    RespuestaRevocacionRol,
    EventoPublico,
)
from app.core.paginacion import Page, PageParams
from app.modules.usuarios.service import (
    iniciar_sesion,
    auditar_acceso,
    RegistroAcceso,
    asignar_rol,
    cambiar_password as cambiar_password_service,
    dar_de_alta_usuario,
    registrar_cliente,
    obtener_historial_roles,
    revocar_rol,
    consultar_eventos,
)

router_publico = APIRouter(prefix="/auth", tags=["Autenticación"])
router_autenticado = APIRouter(prefix="/auth", tags=["Autenticación"])

# D1: una sola instancia por proceso. FastAPI cachea por identidad del callable,
# así que la guarda del router y el parámetro del handler comparten ejecución y
# una única consulta a `asignacion_rol` por petición.
solo_admin = require_roles("ADMIN")

router_admin_usuarios = APIRouter(
    prefix="/usuarios",
    tags=["Administración de usuarios"],
    dependencies=[Depends(solo_admin)],
)
router_admin_eventos = APIRouter(
    prefix="/eventos",
    tags=["Auditoría"],
    dependencies=[Depends(solo_admin)],
)



@router_publico.post("/login", response_model=RespuestaSesion)
async def login(
    solicitud: SolicitudLogin,
    request: Request,
    response: Response,
    sesion: Annotated[AsyncSession, Depends(get_session)],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> RespuestaSesion:
    """
    Inicia sesión con email y contraseña, entrega cookie HttpOnly access_token
    y devuelve la información del usuario autenticado (D4, D15).
    """
    ip = request.client.host if request.client else "desconocida"
    respuesta, token = await iniciar_sesion(
        email=solicitud.email,
        password=solicitud.password,
        ip=ip,
        sesion=sesion,
        sesion_auditoria=sesion_auditoria,
        app_state=request.app.state,
    )
    construir_cookie_sesion(response, token)
    return respuesta


@router_publico.post("/logout", response_model=RespuestaLogout)
async def logout(
    request: Request,
    response: Response,
    sesion: Annotated[AsyncSession, Depends(get_session)],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> RespuestaLogout:
    """
    Cierre de sesión idempotente (D16): borra la cookie access_token.
    Si había una sesión válida, audita el evento LOGOUT.
    """
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = decodificar_token_acceso(token)
            usuario_id = int(payload.get("sub", 0))
            usuario = await sesion.get(Usuario, usuario_id)
            actor = usuario.email if usuario else f"usuario:{usuario_id}"
            ip = request.client.host if request.client else "desconocida"
            await auditar_acceso(
                sesion_auditoria,
                RegistroAcceso(
                    email=actor,
                    ip=ip,
                    actor=actor,
                    accion="LOGOUT",
                    exito=None,
                    cuando=datetime.now(timezone.utc),
                ),
            )
        except Exception:
            # Si el token es inválido, expirado o malformado, logout sigue siendo 200 sin auditar
            pass

    construir_cookie_borrado(response)
    return RespuestaLogout()


@router_publico.post("/registro", status_code=201, response_model=UsuarioRegistrado)
async def registro(
    solicitud: SolicitudRegistro,
    request: Request,
    sesion: Annotated[AsyncSession, Depends(get_session)],
) -> UsuarioRegistrado:
    """
    Auto-registro público (C-17).

    Responde `201` con `UsuarioRegistrado`; `409 EMAIL_DUPLICADO` /
    `DOCUMENTO_DUPLICADO`; `422 ERROR_VALIDACION` si el contrato no cumple.
    """
    return await registrar_cliente(
        solicitud=solicitud,
        app_state=request.app.state,
        sesion=sesion,
    )


@router_autenticado.post(
    "/cambiar-password", response_model=RespuestaCambioPassword
)
async def cambiar_password(
    solicitud: SolicitudCambioPassword,
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
    sesion_cambio: Annotated[
        AsyncSession, Depends(obtener_sesion_cambio_password)
    ],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> RespuestaCambioPassword:
    """
    Cambia la contraseña del usuario autenticado (C-11, D2–D7).

    Exige sesión válida; la contraseña actual incorrecta responde `401`
    uniforme. El `200` no reemite la cookie: por RN-07 el token usado queda
    inválido y el cliente debe volver a autenticarse.
    """
    ip = request.client.host if request.client else "desconocida"
    return await cambiar_password_service(
        usuario=sesion_actual.usuario,
        password_actual=solicitud.password_actual,
        password_nueva=solicitud.password_nueva,
        ip=ip,
        sesion_cambio=sesion_cambio,
        sesion_auditoria=sesion_auditoria,
        app_state=request.app.state,
    )


@router_autenticado.get("/yo", response_model=RespuestaSesion)
async def obtener_sesion_yo(
    sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
    sesion: Annotated[AsyncSession, Depends(get_session)],
) -> RespuestaSesion:
    """
    Consulta de la sesión actual (D11, D15, RN-04).
    Relee los roles vigentes en la base de datos sin confiar en los claims del token.
    """
    usuario = sesion_actual.usuario
    roles_vigentes = await get_roles_vigentes(sesion, usuario.id)

    return RespuestaSesion(
        usuario=UsuarioPublico(
            id=usuario.id,
            email=usuario.email,
            nombre=usuario.nombre,
            debe_cambiar_password=usuario.debe_cambiar_password,
        ),
        roles=roles_vigentes,
        token=TokenInfo(
            iat=sesion_actual.iat.isoformat(),
            exp=sesion_actual.exp,
        ),
    )


# ---------------------------------------------------------------------------
# Administración de usuarios y roles (C-12)
# ---------------------------------------------------------------------------


@router_admin_usuarios.post("", status_code=201, response_model=UsuarioCreado)
async def alta_usuario(
    solicitud: SolicitudAltaUsuario,
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(solo_admin)],
    sesion_admin: Annotated[AsyncSession, Depends(obtener_sesion_admin_usuarios)],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> UsuarioCreado:
    """
    Alta de personal (D3, D4).

    Responde `201` con `UsuarioCreado`; `409 EMAIL_DUPLICADO` si el email ya
    existe; `422 ERROR_VALIDACION` si el contrato no cumple.
    """
    ip = request.client.host if request.client else "desconocida"
    return await dar_de_alta_usuario(
        solicitud=solicitud,
        admin=sesion_actual.usuario,
        ip=ip,
        sesion_admin=sesion_admin,
        sesion_auditoria=sesion_auditoria,
        app_state=request.app.state,
    )


@router_admin_usuarios.get("/{usuario_id}/roles", response_model=HistorialRoles)
async def consultar_roles_usuario(
    usuario_id: int,
    sesion_actual: Annotated[SesionActual, Depends(solo_admin)],
    sesion: Annotated[AsyncSession, Depends(get_session)],
) -> HistorialRoles:
    """
    Historial de asignaciones del usuario (D5).

    Devuelve vigentes y revocadas ordenadas por `desde` descendente; `404
    USUARIO_NO_ENCONTRADO` si el `id` no existe.
    """
    return await obtener_historial_roles(sesion, usuario_id)


@router_admin_usuarios.post("/{usuario_id}/roles", status_code=201, response_model=AsignacionRolPublica)
async def asignar_rol_usuario(
    usuario_id: int,
    solicitud: SolicitudAsignacionRol,
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(solo_admin)],
    sesion_admin: Annotated[AsyncSession, Depends(obtener_sesion_admin_usuarios)],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> AsignacionRolPublica:
    """
    Asignación de rol con vencimiento opcional (D6).

    `201` con la asignación creada; `404 USUARIO_NO_ENCONTRADO`; `409
    ROL_YA_ASIGNADO` (RN-03); `422 ERROR_VALIDACION` si el rol o el vencimiento
    no son válidos.
    """
    ip = request.client.host if request.client else "desconocida"
    return await asignar_rol(
        usuario_id=usuario_id,
        solicitud=solicitud,
        admin=sesion_actual.usuario,
        ip=ip,
        sesion_admin=sesion_admin,
        sesion_auditoria=sesion_auditoria,
    )


@router_admin_usuarios.delete("/{usuario_id}/roles/{rol}", response_model=RespuestaRevocacionRol)
async def revocar_rol_usuario(
    usuario_id: int,
    rol: str,
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(solo_admin)],
    sesion_admin: Annotated[AsyncSession, Depends(obtener_sesion_admin_usuarios)],
    sesion_auditoria: Annotated[AsyncSession, Depends(obtener_sesion_auditoria)],
) -> RespuestaRevocacionRol:
    ip = request.client.host if request.client else "desconocida"
    return await revocar_rol(
        sesion_admin=sesion_admin,
        sesion_auditoria=sesion_auditoria,
        usuario_id=usuario_id,
        rol=rol,
        admin=sesion_actual.usuario,
        ip=ip,
    )


@router_admin_eventos.get("", response_model=Page[EventoPublico])
async def listar_eventos_auditoria(
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(solo_admin)],
    sesion: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    actor: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> Page[EventoPublico]:
    return await consultar_eventos(
        sesion,
        desde=desde,
        hasta=hasta,
        actor=actor,
        pagina=page,
        tamanio=size,
    )
