"""
Suite del cableado de las rutas administrativas (C-12, grupo 2).

Cubre el registro de los cinco endpoints (D1), que sin cookie responden `401`,
que el grupo protegido las exige con contraseña actualizada y que la guarda
`solo_admin` se construye una sola vez y emite una única consulta a
`asignacion_rol` por petición.

Los tests marcados como integración requieren PostgreSQL real (regla dura #9).
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import event, select

import main
from main import app
from app.modules.usuarios.models import AsignacionRol
from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)

RUTAS_ADMIN = [
    ("POST", "/usuarios"),
    ("GET", "/usuarios/{usuario_id}/roles"),
    ("POST", "/usuarios/{usuario_id}/roles"),
    ("DELETE", "/usuarios/{usuario_id}/roles/{rol}"),
    ("GET", "/eventos"),
]

PETICIONES_SIN_COOKIE = [
    ("post", "/usuarios"),
    ("get", "/usuarios/1/roles"),
    ("post", "/usuarios/1/roles"),
    ("delete", "/usuarios/1/roles/RECEPCION"),
    ("get", "/eventos"),
]


def _aplanar_rutas(contenedor) -> list[APIRoute]:
    """Devuelve los `APIRoute` de un router o app, resolviendo routers incluidos."""
    rutas: list[APIRoute] = []
    for ruta in contenedor.routes:
        if isinstance(ruta, APIRoute):
            rutas.append(ruta)
        else:
            interno = getattr(ruta, "original_router", None)
            if interno is not None:
                rutas.extend(_aplanar_rutas(interno))
    return rutas


def _pares_metodo_ruta(contenedor) -> set[tuple[str, str]]:
    return {
        (metodo, ruta.path)
        for ruta in _aplanar_rutas(contenedor)
        for metodo in ruta.methods
        if metodo not in {"HEAD", "OPTIONS"}
    }


# ---------------------------------------------------------------------------
# Registro y montaje (sin base de datos)
# ---------------------------------------------------------------------------


def test_los_cinco_endpoints_estan_registrados_en_la_app() -> None:
    assert set(RUTAS_ADMIN) <= _pares_metodo_ruta(app)


def test_los_endpoints_estan_en_el_grupo_protegido_y_no_en_el_publico() -> None:
    protegido = _pares_metodo_ruta(main.router_protegido)
    publico = _pares_metodo_ruta(main.router_publico)

    assert set(RUTAS_ADMIN) <= protegido
    assert set(RUTAS_ADMIN).isdisjoint(publico)


def test_una_app_limpia_monta_las_rutas_administrativas() -> None:
    app_limpia = main.create_app()

    assert set(RUTAS_ADMIN) <= _pares_metodo_ruta(app_limpia)


def test_solo_admin_se_construye_una_sola_vez_por_router() -> None:
    from app.modules.usuarios import router as router_usuarios

    guarda_usuarios = router_usuarios.router_admin_usuarios.dependencies[0].dependency
    guarda_eventos = router_usuarios.router_admin_eventos.dependencies[0].dependency

    assert guarda_usuarios is router_usuarios.solo_admin
    assert guarda_eventos is router_usuarios.solo_admin


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo, ruta", PETICIONES_SIN_COOKIE)
async def test_sin_cookie_devuelve_401(metodo: str, ruta: str) -> None:
    async with cliente_http() as cliente:
        respuesta = await getattr(cliente, metodo)(ruta)

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "CREDENCIALES_INVALIDAS"


def test_sin_cookie_devuelve_el_cuerpo_uniforme() -> None:
    async def _ejecutar():
        async with cliente_http() as cliente:
            return await cliente.get("/eventos")

    respuesta = asyncio.run(_ejecutar())

    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "detail": "Credenciales inválidas",
        "codigo": "CREDENCIALES_INVALIDAS",
    }


# ---------------------------------------------------------------------------
# Autorización con base de datos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo, ruta", PETICIONES_SIN_COOKIE)
async def test_sin_rol_admin_devuelve_403(
    contexto_auth, metodo: str, ruta: str
) -> None:
    usuario = await crear_usuario_prueba(contexto_auth, "solo-mecanico@taller.test")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "MECANICO")

    async with cliente_http(token_de_sesion(usuario.id, ["MECANICO"])) as cliente:
        respuesta = await getattr(cliente, metodo)(ruta)

    assert respuesta.status_code == 403
    assert respuesta.json() == {
        "detail": "Permisos insuficientes",
        "codigo": "PERMISOS_INSUFICIENTES",
    }


@pytest.mark.asyncio
async def test_admin_revocado_despues_del_token_pierde_acceso(contexto_auth) -> None:
    admin, token = await crear_admin_prueba(contexto_auth, "admin-revocado@taller.test")

    async with cliente_http(token) as cliente:
        assert (await cliente.get("/eventos")).status_code == 200

        asignacion = (
            await contexto_auth.execute(
                select(AsignacionRol).where(
                    AsignacionRol.usuario_id == admin.id,
                    AsignacionRol.rol == "ADMIN",
                )
            )
        ).scalars().first()
        asignacion.revocada_en = datetime.now(timezone.utc)
        await contexto_auth.flush()

        respuesta = await cliente.get("/eventos")

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "PERMISOS_INSUFICIENTES"


@pytest.mark.asyncio
async def test_admin_con_password_provisoria_recibe_403(contexto_auth) -> None:
    admin = await crear_usuario_prueba(
        contexto_auth,
        "admin-provisorio@taller.test",
        debe_cambiar_password=True,
    )
    await crear_asignacion_prueba(contexto_auth, admin.id, "ADMIN")

    async with cliente_http(token_de_sesion(admin.id, ["ADMIN"])) as cliente:
        respuesta = await cliente.get("/eventos")

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"


@pytest.mark.asyncio
async def test_la_guarda_admin_emite_una_sola_consulta_por_peticion(
    contexto_auth,
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-una-consulta@taller.test")
    await contexto_auth.flush()

    sentencias: list[str] = []

    def _registrar(conn, cursor, statement, parameters, context, executemany):
        if "asignacion_rol" in statement:
            sentencias.append(statement)

    conexion = contexto_auth.bind
    objetivo = getattr(conexion, "sync_engine", None) or conexion.sync_connection
    event.listen(objetivo, "before_cursor_execute", _registrar)
    try:
        async with cliente_http(token) as cliente:
            respuesta = await cliente.get("/eventos")
    finally:
        event.remove(objetivo, "before_cursor_execute", _registrar)

    assert respuesta.status_code == 200
    assert len(sentencias) == 1
