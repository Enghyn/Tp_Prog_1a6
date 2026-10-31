"""
Suite de `POST /usuarios/{id}/roles` (C-12, grupo 5).

Contrato: asignación abierta con `desde = now()`, `otorgada_por` = administrador
autenticado y `vence_en` opcional futuro (D6); `409 ROL_YA_ASIGNADO` si ya hay
una asignación vigente del mismo rol (RN-03) y cierre de la vencida antes de
abrir la fila nueva.

Los tests de contrato Pydantic corren sin base; los HTTP usan PostgreSQL real.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.modules.usuarios.models import AsignacionRol
from app.modules.usuarios.schemas import SolicitudAsignacionRol
from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    sonda_roles,
    token_de_sesion,
)

FUTURO = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
PASADO = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Contrato Pydantic (sin base de datos)
# ---------------------------------------------------------------------------


def test_solicitud_asignacion_sin_vencimiento_es_valida() -> None:
    solicitud = SolicitudAsignacionRol(rol="RECEPCION")

    assert solicitud.rol == "RECEPCION"
    assert solicitud.vence_en is None


def test_solicitud_asignacion_con_vencimiento_futuro_conserva_el_instante() -> None:
    instante = datetime(2030, 5, 1, 9, 30, 0, 123456, tzinfo=timezone(timedelta(hours=-3)))

    solicitud = SolicitudAsignacionRol(rol="MECANICO", vence_en=instante)

    assert solicitud.vence_en == instante
    assert solicitud.vence_en.utcoffset() == timedelta(hours=-3)


@pytest.mark.parametrize("rol", ["GERENTE", "admin", "", "CLIENTE "])
def test_solicitud_asignacion_con_rol_fuera_del_catalogo_falla(rol: str) -> None:
    with pytest.raises(ValidationError):
        SolicitudAsignacionRol(rol=rol)


def test_solicitud_asignacion_con_vencimiento_pasado_falla() -> None:
    with pytest.raises(ValidationError):
        SolicitudAsignacionRol(rol="MECANICO", vence_en=PASADO)


def test_solicitud_asignacion_con_vencimiento_sin_zona_horaria_falla() -> None:
    with pytest.raises(ValidationError):
        SolicitudAsignacionRol(rol="MECANICO", vence_en=datetime(2030, 1, 1, 12, 0, 0))


def test_solicitud_asignacion_con_campo_extra_falla() -> None:
    with pytest.raises(ValidationError):
        SolicitudAsignacionRol(rol="MECANICO", otorgada_por=1)


# ---------------------------------------------------------------------------
# Asignación exitosa (HTTP + PostgreSQL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asignacion_sin_vencimiento_devuelve_201(contexto_auth) -> None:
    admin, token = await crear_admin_prueba(contexto_auth, "admin-asigna@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "asignado@taller.test")

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            f"/usuarios/{usuario.id}/roles", json={"rol": "RECEPCION"}
        )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "RECEPCION"
    assert cuerpo["vence_en"] is None
    assert cuerpo["revocada_en"] is None
    assert cuerpo["otorgada_por"] == admin.id
    assert cuerpo["vigente"] is True
    assert cuerpo["desde"] is not None

    fila = await contexto_auth.get(AsignacionRol, cuerpo["id"])
    assert fila is not None
    assert fila.usuario_id == usuario.id
    assert fila.otorgada_por == admin.id


@pytest.mark.asyncio
async def test_asignacion_con_vencimiento_no_utc_conserva_el_instante(
    contexto_auth,
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-vence@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "vence@taller.test")
    instante = datetime(
        2031, 3, 4, 10, 20, 30, 654321, tzinfo=timezone(timedelta(hours=-3))
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            f"/usuarios/{usuario.id}/roles",
            json={"rol": "MECANICO", "vence_en": instante.isoformat()},
        )

    assert respuesta.status_code == 201
    devuelto = datetime.fromisoformat(respuesta.json()["vence_en"])
    assert devuelto == instante
    assert devuelto.microsecond == instante.microsecond


@pytest.mark.asyncio
async def test_la_asignacion_habilita_la_autorizacion_sin_reemitir_token(
    contexto_auth, montar_sonda
) -> None:
    _, token_admin = await crear_admin_prueba(contexto_auth, "admin-sonda@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "sonda-recepcion@taller.test")
    montar_sonda(sonda_roles("RECEPCION", ruta="/sonda/recepcion"))

    async with cliente_http(token_de_sesion(usuario.id)) as cliente:
        antes = await cliente.get("/sonda/recepcion")

        async with cliente_http(token_admin) as cliente_admin:
            asignacion = await cliente_admin.post(
                f"/usuarios/{usuario.id}/roles", json={"rol": "RECEPCION"}
            )

        despues = await cliente.get("/sonda/recepcion")

    assert asignacion.status_code == 201
    assert antes.status_code == 403
    assert despues.status_code == 200
    assert despues.json() == {"usuario_id": usuario.id}


@pytest.mark.asyncio
async def test_asignacion_audita_rol_asignado(contexto_auth) -> None:
    from app.modules.usuarios.models import EventoSeguridad

    admin, token = await crear_admin_prueba(contexto_auth, "admin-audita-rol@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "auditado-rol@taller.test")

    async with cliente_http(token) as cliente:
        await cliente.post(f"/usuarios/{usuario.id}/roles", json={"rol": "MECANICO"})

    eventos = (
        await contexto_auth.execute(
            select(EventoSeguridad).where(EventoSeguridad.accion == "ROL_ASIGNADO")
        )
    ).scalars().all()
    assert [evento.actor for evento in eventos] == [admin.email]


# ---------------------------------------------------------------------------
# Errores de dominio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asignacion_a_usuario_inexistente_devuelve_404(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-404@taller.test")
    total_antes = await contexto_auth.scalar(select(func.count(AsignacionRol.id)))

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post("/usuarios/999999/roles", json={"rol": "MECANICO"})

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "detail": "Usuario no encontrado",
        "codigo": "USUARIO_NO_ENCONTRADO",
    }
    assert await contexto_auth.scalar(select(func.count(AsignacionRol.id))) == total_antes


@pytest.mark.asyncio
async def test_doble_asignacion_vigente_devuelve_409_sin_alterar_la_original(
    contexto_auth,
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-rn03@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "rn03@taller.test")
    desde = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    vence = datetime(2030, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    original = await crear_asignacion_prueba(
        contexto_auth, usuario.id, "RECEPCION", desde=desde, vence_en=vence
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            f"/usuarios/{usuario.id}/roles", json={"rol": "RECEPCION"}
        )

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "detail": "El usuario ya tiene ese rol vigente",
        "codigo": "ROL_YA_ASIGNADO",
    }

    filas = (
        await contexto_auth.execute(
            select(AsignacionRol).where(
                AsignacionRol.usuario_id == usuario.id,
                AsignacionRol.rol == "RECEPCION",
            )
        )
    ).scalars().all()
    abiertas = [fila for fila in filas if fila.revocada_en is None]
    assert len(abiertas) == 1
    assert abiertas[0].id == original.id
    assert abiertas[0].desde == desde
    assert abiertas[0].vence_en == vence


@pytest.mark.asyncio
async def test_reasignacion_de_rol_vencido_cierra_y_abre_fila_nueva(
    contexto_auth,
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-vencido@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "rol-vencido@taller.test")
    anterior = await crear_asignacion_prueba(
        contexto_auth,
        usuario.id,
        "MECANICO",
        desde=PASADO,
        vence_en=PASADO + timedelta(minutes=1),
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(
            f"/usuarios/{usuario.id}/roles", json={"rol": "MECANICO"}
        )
        historial = await cliente.get(f"/usuarios/{usuario.id}/roles")

    assert respuesta.status_code == 201
    nueva_id = respuesta.json()["id"]
    assert nueva_id != anterior.id

    await contexto_auth.refresh(anterior)
    assert anterior.revocada_en is not None

    filas = historial.json()["asignaciones"]
    assert [fila["id"] for fila in filas] == [nueva_id, anterior.id]
    assert [fila["vigente"] for fila in filas] == [True, False]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cuerpo",
    [
        {"rol": "GERENTE"},
        {"rol": "MECANICO", "vence_en": PASADO.isoformat()},
        {"rol": "MECANICO", "otorgada_por": 1},
    ],
)
async def test_asignacion_invalida_devuelve_422_sin_crear_filas(
    contexto_auth, cuerpo: dict
) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-422-rol@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "invalida@taller.test")
    total_antes = await contexto_auth.scalar(select(func.count(AsignacionRol.id)))

    async with cliente_http(token) as cliente:
        respuesta = await cliente.post(f"/usuarios/{usuario.id}/roles", json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "ERROR_VALIDACION"
    assert await contexto_auth.scalar(select(func.count(AsignacionRol.id))) == total_antes

# ---------------------------------------------------------------------------
# RN-05: autoproccion del ultimo administrador
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revocar_propio_rol_admin_devuelve_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    await contexto_auth.flush()
    async with cliente_http(token) as c:
        r = await c.delete(f"/usuarios/{admin.id}/roles/ADMIN")
        assert r.status_code == 409
