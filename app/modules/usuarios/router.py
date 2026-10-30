from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import SesionActual, obtener_usuario_actual
from app.core.seguridad import (
    construir_cookie_sesion,
    construir_cookie_borrado,
    decodificar_token_acceso,
)
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import obtener_sesion_auditoria
from app.modules.usuarios.schemas import (
    SolicitudLogin,
    RespuestaSesion,
    RespuestaLogout,
    UsuarioPublico,
    TokenInfo,
)
from app.modules.usuarios.service import (
    iniciar_sesion,
    obtener_roles_vigentes,
    auditar_acceso,
    RegistroAcceso,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=RespuestaSesion)
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


@router.post("/logout", response_model=RespuestaLogout)
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


@router.get("/yo", response_model=RespuestaSesion)
async def obtener_sesion_yo(
    sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
) -> RespuestaSesion:
    """
    Consulta de la sesión actual (D11, D15, RN-04).
    Relee los roles vigentes en la base de datos sin confiar en los claims del token.
    """
    usuario = sesion_actual.usuario
    ahora = datetime.now(timezone.utc)
    roles_vigentes = obtener_roles_vigentes(usuario.asignaciones, ahora)

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
