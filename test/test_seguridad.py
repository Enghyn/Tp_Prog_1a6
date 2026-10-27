import os
import asyncio
import pytest

os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

from app.core.seguridad import (
    hash_password,
    verify_password_async,
    hash_password_sync,
    generar_hash_ficticio,
    verify_password_o_dummy,
)


@pytest.mark.asyncio
async def test_hash_y_verificacion():
    contrasena = "mi_contrasena_segura"
    hash_generado = await hash_password(contrasena)
    resultado = await verify_password_async(contrasena, hash_generado)
    assert resultado is True
    resultado_malo = await verify_password_async("contrasena_erronea", hash_generado)
    assert resultado_malo is False


@pytest.mark.asyncio
async def test_verificaciones_concurrentes():
    hash_generado = await hash_password("test123")
    tareas = [verify_password_async("test123", hash_generado) for _ in range(20)]
    resultados = await asyncio.gather(*tareas)
    assert all(r is True for r in resultados)


@pytest.mark.asyncio
async def test_hash_ficticio_siempre_retorna_false():
    hash_ficticio = generar_hash_ficticio()
    resultado = await verify_password_o_dummy("cualquier_contrasena", None, hash_ficticio)
    assert resultado is False


def test_hash_password_sync():
    contrasena = "test_sync"
    hash_generado = hash_password_sync(contrasena)
    import bcrypt
    assert bcrypt.checkpw(contrasena.encode("utf-8"), hash_generado.encode("utf-8"))
