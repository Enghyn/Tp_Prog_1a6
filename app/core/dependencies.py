from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.errors import NoAutenticadoError
from app.core.seguridad import decodificar_token_acceso
from app.modules.usuarios.models import Usuario


@dataclass(frozen=True)
class SesionActual:
    """
    Representa la sesión activa resuelta a partir del JWT y la base de datos (D11).
    """
    usuario: Usuario
    iat: datetime
    exp: int


def token_anterior_al_cambio(iat: datetime, password_cambiada_en: datetime | None) -> bool:
    """
    Evalúa con precisión de microsegundos si el token fue emitido antes del último
    cambio de contraseña (RN-07, D6).
    """
    if password_cambiada_en is None:
        return False
    if iat.tzinfo is None:
        iat = iat.replace(tzinfo=timezone.utc)
    if password_cambiada_en.tzinfo is None:
        password_cambiada_en = password_cambiada_en.replace(tzinfo=timezone.utc)
    return iat < password_cambiada_en


async def obtener_usuario_actual(
    request: Request,
    sesion: Annotated[AsyncSession, Depends(get_session)],
) -> SesionActual:
    """
    Resuelve al usuario actual a partir de la cookie HttpOnly access_token.
    Valida firma, expiración, estado activo y concordancia con password_cambiada_en.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")

    payload = decodificar_token_acceso(token)
    try:
        usuario_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")

    usuario = await sesion.get(Usuario, usuario_id, options=[selectinload(Usuario.asignaciones)])
    if not usuario or not usuario.activo:
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")

    iat = payload["iat"]
    if token_anterior_al_cambio(iat, usuario.password_cambiada_en):
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")

    return SesionActual(
        usuario=usuario,
        iat=iat,
        exp=payload["exp"],
    )
