import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from fastapi import Response
from app.core.configuracion import configuracion, Configuracion
from app.core.errors import NoAutenticadoError


async def hash_password(contrasena: str, app_state=None) -> str:
    semaforo = None
    if app_state is not None:
        semaforo = getattr(app_state, "bcrypt_semaforo", None)
    
    if semaforo is not None:
        async with semaforo:
            return await asyncio.to_thread(_hash_password_sincrono, contrasena)
    else:
        return await asyncio.to_thread(_hash_password_sincrono, contrasena)


def _hash_password_sincrono(contrasena: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(contrasena.encode("utf-8"), salt).decode("utf-8")


def hash_password_sync(contrasena: str) -> str:
    """Uso exclusivo para seed.py o CLI. Nunca usar en handlers async."""
    return _hash_password_sincrono(contrasena)


def verify_password(contrasena: str, hash_contrasena: str, app_state=None) -> bool:
    semaforo = None
    if app_state is not None:
        semaforo = getattr(app_state, "bcrypt_semaforo", None)
    
    if semaforo is not None:
        async def _verificar():
            async with semaforo:
                return await asyncio.to_thread(_verify_password_sincrono, contrasena, hash_contrasena)
        return _verificar()
    else:
        return asyncio.to_thread(_verify_password_sincrono, contrasena, hash_contrasena)


async def verify_password_async(contrasena: str, hash_contrasena: str, app_state=None) -> bool:
    semaforo = None
    if app_state is not None:
        semaforo = getattr(app_state, "bcrypt_semaforo", None)
    
    if semaforo is not None:
        async with semaforo:
            return await asyncio.to_thread(_verify_password_sincrono, contrasena, hash_contrasena)
    else:
        return await asyncio.to_thread(_verify_password_sincrono, contrasena, hash_contrasena)


def _verify_password_sincrono(contrasena: str, hash_contrasena: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_contrasena.encode("utf-8"))
    except Exception:
        return False


def generar_hash_ficticio() -> str:
    return _hash_password_sincrono("hash_ficticio_para_proteccion_enumeracion")


async def verify_password_o_dummy(contrasena: str, hash_real: str | None, hash_ficticio: str, app_state=None) -> bool:
    hash_a_usar = hash_real if hash_real is not None else hash_ficticio
    if hash_real is None:
        await verify_password_async(contrasena, hash_a_usar, app_state)
        return False
    return await verify_password_async(contrasena, hash_a_usar, app_state)


# Alias para compatibilidad
hash_contrasena = hash_password
verificar_contrasena = verify_password
generar_hash_dummy = generar_hash_ficticio
verificar_contrasena_o_dummy = verify_password_o_dummy
hash_contrasena_sync = hash_password_sync


def crear_token_acceso(usuario_id: int, roles: list[str], iat: datetime) -> str:
    """
    Emite un JWT firmado con HS256 y configuracion.jwt_secret.
    Claims:
      - sub: string con usuario_id
      - roles: lista de strings (informativos, RN-04)
      - iat: string ISO-8601 con microsegundos (RN-07, D6)
      - exp: timestamp UNIX entero (iat + access_token_ttl_min)
    """
    if iat.tzinfo is None:
        iat = iat.replace(tzinfo=timezone.utc)
    exp = int((iat + timedelta(minutes=configuracion.access_token_ttl_min)).timestamp())
    payload = {
        "sub": str(usuario_id),
        "roles": roles,
        "iat": iat.isoformat(),
        "exp": exp,
    }
    return jwt.encode(payload, configuracion.jwt_secret, algorithm="HS256")


def _parsear_iat(valor: Any) -> datetime:
    """
    Parsea el claim iat manteniendo precisión de microsegundos (RN-07, D6).
    Acepta string ISO-8601 o timestamp numérico defensivo.
    """
    if isinstance(valor, str):
        dt = datetime.fromisoformat(valor)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    elif isinstance(valor, (int, float)):
        return datetime.fromtimestamp(valor, tz=timezone.utc)
    raise ValueError("Formato de iat no soportado")


def decodificar_token_acceso(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un token de sesión HS256.
    Fija algorithms=['HS256'], options con sub, exp, iat requeridos, y leeway=0 (D10).
    Lanza NoAutenticadoError uniforme ante cualquier anomalía o expiración (D9).
    """
    try:
        payload = jwt.decode(
            token,
            configuracion.jwt_secret,
            algorithms=["HS256"],
            options={
                "require": ["exp", "iat", "sub"],
                "verify_exp": True,
                "verify_iat": False,
            },
            leeway=0,
        )
        payload["iat"] = _parsear_iat(payload["iat"])
        return payload
    except Exception:
        raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")


def determinar_cookie_secure(config: Configuracion | None = None) -> bool:
    """
    Determina si la cookie de sesión debe llevar el atributo Secure.
    Si se configuró COOKIE_SECURE explícito, se respeta prioritariamente.
    De lo contrario, se deriva del entorno (dev, local, test -> False; produccion u otros -> True).
    """
    cfg = config or configuracion
    if cfg.cookie_secure is not None:
        return bool(cfg.cookie_secure)
    return cfg.entorno.strip().lower() not in {"dev", "local", "test"}


def construir_cookie_sesion(
    respuesta: Response,
    token: str,
    config: Configuracion | None = None,
) -> None:
    """
    Establece la cookie access_token con HttpOnly, SameSite=Lax, Path=/,
    Max-Age y Secure según D7 y configuración.
    """
    cfg = config or configuracion
    secure = determinar_cookie_secure(cfg)
    max_age = cfg.access_token_ttl_min * 60
    respuesta.set_cookie(
        key="access_token",
        value=token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def construir_cookie_borrado(
    respuesta: Response,
    config: Configuracion | None = None,
) -> None:
    """
    Instrucción de borrado de cookie de sesión con exactamente los mismos atributos (D7, D16).
    """
    cfg = config or configuracion
    secure = determinar_cookie_secure(cfg)
    respuesta.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )
