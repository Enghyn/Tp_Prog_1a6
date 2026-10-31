from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import NoAutenticadoError, ProhibidoError
from app.core.seguridad import decodificar_token_acceso
from app.modules.clientes.repository import (
    es_duenio_de_vehiculo as _es_duenio_de_vehiculo,
)
from app.modules.ordenes.repository import (
    es_duenio_de_orden as _es_duenio_de_orden,
)
from app.modules.usuarios.models import ROLES_VALIDOS, Usuario
from app.modules.usuarios.repository import obtener_roles_vigentes_por_usuario


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


async def get_roles_vigentes(sesion: AsyncSession, usuario_id: int) -> list[str]:
    """
    Fachada estable para leer los roles vigentes de un usuario (D1).

    Delega la consulta en el repositorio de usuarios, que es dueño del esquema
    de `asignacion_rol`. No hay caché entre requests: RN-04 exige releer la
    base en cada decisión de autorización.
    """
    return await obtener_roles_vigentes_por_usuario(sesion, usuario_id)


def require_roles(*roles: str) -> Callable[..., Awaitable[SesionActual]]:
    """
    Construye una dependencia de FastAPI que exige al menos uno de los roles
    indicados, leyendo los roles vigentes de la base en cada petición (RN-04).

    Los roles desconocidos fallan al construir la dependencia (al importar el
    router), no al atender una petición.

    Uso por router:

        router = APIRouter(
            prefix="/ordenes",
            dependencies=[Depends(require_roles("ADMIN", "RECEPCION"))],
        )

    Uso por endpoint (devuelve la sesión para reutilizarla en el handler):

        @router.delete("/{orden_id}")
        async def cancelar(
            sesion_actual: SesionActual = Depends(require_roles("CLIENTE")),
        ) -> None:
            ...

    Args:
        *roles: roles del catálogo `ROLES_VALIDOS` que autorizan la petición.

    Raises:
        ValueError: si algún rol no pertenece al catálogo.
    """
    requeridos = frozenset(roles)
    desconocidos = requeridos - set(ROLES_VALIDOS)
    if desconocidos:
        raise ValueError(f"Roles desconocidos: {sorted(desconocidos)}")

    async def verificar(
        sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
        sesion: Annotated[AsyncSession, Depends(get_session)],
    ) -> SesionActual:
        roles_vigentes = await get_roles_vigentes(sesion, sesion_actual.usuario.id)
        if requeridos.isdisjoint(roles_vigentes):
            raise ProhibidoError("Permisos insuficientes", "PERMISOS_INSUFICIENTES")
        return sesion_actual

    return verificar


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

    usuario = await sesion.get(Usuario, usuario_id)
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


async def es_duenio_de_vehiculo(
    sesion: AsyncSession,
    usuario_id: int,
    vehiculo_id: int,
) -> bool:
    """
    Fachada de RN-17 para vehículos (D1). Devuelve `bool`; el endpoint decide
    si un `False` se traduce en `403` o `404`.
    """
    return await _es_duenio_de_vehiculo(sesion, usuario_id, vehiculo_id)


async def es_duenio_de_orden(
    sesion: AsyncSession,
    usuario_id: int,
    orden_id: int,
) -> bool:
    """
    Fachada de RN-17 para órdenes de trabajo (D1). Devuelve `bool`; el endpoint
    decide si un `False` se traduce en `403` o `404`.
    """
    return await _es_duenio_de_orden(sesion, usuario_id, orden_id)


async def requiere_password_actualizada(
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
) -> None:
    """
    Gating de RN-06: bloquea las rutas de dominio cuando el usuario tiene una
    contraseña provisoria pendiente de cambio.

    Las rutas `/auth/*` y `/health/*` quedan exentas por prefijo, de modo que
    C-11 (`POST /auth/cambiar-password`) y el propio `/auth/yo` sigan operativas.
    Sin cookie, `obtener_usuario_actual` responde `401` antes de evaluar la
    bandera; con cookie válida y bandera activa se responde `403`.
    """
    ruta = request.url.path
    if ruta.startswith("/auth/") or ruta.startswith("/health/"):
        return
    if sesion_actual.usuario.debe_cambiar_password:
        raise ProhibidoError(
            "Cambio de contraseña requerido", "CAMBIO_PASSWORD_REQUERIDO"
        )
