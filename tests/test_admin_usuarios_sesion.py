"""
Suite de la sesión dedicada de administración de usuarios (C-12, grupo 2).

`obtener_sesion_admin_usuarios` aísla las escrituras de dominio del ciclo de
vida del request, siguiendo el patrón de C-11 (D2). El override del fixture
`contexto_auth` la ata a la transacción externa para que el rollback del test
borre todo lo escrito.

Los tests de integración requieren PostgreSQL real (regla dura #9); sin base
quedan `skipped`.
"""

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import obtener_sesion_admin_usuarios
from main import app


class FabricaSesionesEspia:
    """Fábrica mínima: devuelve un contexto asíncrono con un nombre de sesión."""

    def __init__(self) -> None:
        self.llamadas = 0

    def __call__(self):
        fabrica = self

        class ContextoFalso:
            async def __aenter__(self) -> str:
                fabrica.llamadas += 1
                return f"sesion-{fabrica.llamadas}"

            async def __aexit__(self, *args: object) -> bool:
                return False

        return ContextoFalso()


def _request_con_fabrica(fabrica) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_maker=fabrica))
    )


def _sonda_escritura(ruta: str) -> APIRouter:
    sonda = APIRouter()

    @sonda.post(ruta)
    async def endpoint(
        sesion_admin: AsyncSession = Depends(obtener_sesion_admin_usuarios),
    ) -> dict[str, int]:
        usuario = Usuario(
            email="sonda-sesion-admin@taller.test",
            nombre="Sonda",
            password_hash="hash-de-prueba",
        )
        sesion_admin.add(usuario)
        await sesion_admin.flush()
        return {"id": usuario.id}

    return sonda


# ---------------------------------------------------------------------------
# Dependencia: fábrica inyectada y fallback al módulo (sin base de datos)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sesion_admin_usuarios_usa_la_fabrica_del_app_state() -> None:
    fabrica = FabricaSesionesEspia()
    generador = obtener_sesion_admin_usuarios(_request_con_fabrica(fabrica))

    sesion = await generador.__anext__()

    assert sesion == "sesion-1"
    assert fabrica.llamadas == 1
    await generador.aclose()


@pytest.mark.asyncio
async def test_sesion_admin_usuarios_cae_a_la_fabrica_del_modulo(monkeypatch) -> None:
    from app.modules.usuarios import repository

    fabrica = FabricaSesionesEspia()
    monkeypatch.setattr(repository, "session_maker", fabrica)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    generador = repository.obtener_sesion_admin_usuarios(request)
    sesion = await generador.__anext__()

    assert sesion == "sesion-1"
    await generador.aclose()


def test_sesion_admin_usuarios_documenta_la_deuda_de_c14() -> None:
    docstring = obtener_sesion_admin_usuarios.__doc__ or ""

    assert "UnitOfWork" in docstring or "C-14" in docstring


# ---------------------------------------------------------------------------
# Integración: la sesión dedicada vive dentro de la transacción del fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contexto_auth_overridea_la_sesion_admin_usuarios(contexto_auth) -> None:
    assert obtener_sesion_admin_usuarios in app.dependency_overrides


@pytest.mark.asyncio
async def test_sesion_admin_usuarios_comparte_la_transaccion_del_fixture(
    contexto_auth, montar_sonda, monkeypatch
) -> None:
    def _fabrica_prohibida():
        raise AssertionError("La dependencia no fue overridden en contexto_auth")

    monkeypatch.setattr(app.state, "session_maker", _fabrica_prohibida, raising=False)
    montar_sonda(_sonda_escritura("/sonda/sesion-admin"))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        respuesta = await cliente.post("/sonda/sesion-admin")

    assert respuesta.status_code == 200
    fila = (
        await contexto_auth.execute(
            select(Usuario).where(Usuario.email == "sonda-sesion-admin@taller.test")
        )
    ).scalars().first()
    assert fila is not None
    assert fila.id == respuesta.json()["id"]


def test_las_rutas_de_la_sonda_no_quedan_montadas() -> None:
    rutas = {ruta.path for ruta in app.router.routes if isinstance(ruta, APIRoute)}

    assert "/sonda/sesion-admin" not in rutas
