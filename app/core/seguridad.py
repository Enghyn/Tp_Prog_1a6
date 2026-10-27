import asyncio
import bcrypt


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
