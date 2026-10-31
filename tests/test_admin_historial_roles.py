"""
Suite de `GET /usuarios/{id}/roles` (C-12, grupo 4).

Contrato: historial completo de asignaciones (vigentes y revocadas) ordenado
por `desde` descendente con la marca `vigente` calculada con un único `ahora`
por request (D5).

El predicado de vigencia es puro y se prueba sin base; los casos HTTP usan
PostgreSQL real (regla dura #9).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.usuarios.models import AsignacionRol
from app.modules.usuarios.service import es_asignacion_vigente
from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
)

AHORA = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)


def _asignacion(
    *,
    rol: str = "MECANICO",
    desde: datetime | None = None,
    vence_en: datetime | None = None,
    revocada_en: datetime | None = None,
) -> AsignacionRol:
    return AsignacionRol(
        usuario_id=1,
        rol=rol,
        desde=desde or AHORA,
        vence_en=vence_en,
        revocada_en=revocada_en,
    )


# ---------------------------------------------------------------------------
# Predicado de vigencia (sin base de datos)
# ---------------------------------------------------------------------------


def test_asignacion_sin_vencimiento_ni_revocacion_es_vigente() -> None:
    assert es_asignacion_vigente(_asignacion(), AHORA) is True


def test_asignacion_con_vencimiento_futuro_es_vigente() -> None:
    assert (
        es_asignacion_vigente(_asignacion(vence_en=AHORA + timedelta(seconds=1)), AHORA)
        is True
    )


def test_asignacion_con_vencimiento_exacto_no_es_vigente() -> None:
    assert es_asignacion_vigente(_asignacion(vence_en=AHORA), AHORA) is False


def test_asignacion_vencida_no_es_vigente() -> None:
    assert (
        es_asignacion_vigente(_asignacion(vence_en=AHORA - timedelta(seconds=1)), AHORA)
        is False
    )


def test_asignacion_revocada_no_es_vigente() -> None:
    assert (
        es_asignacion_vigente(_asignacion(revocada_en=AHORA), AHORA) is False
    )


def test_asignacion_con_fechas_sin_zona_se_interpreta_en_utc() -> None:
    ingenua = datetime(2026, 10, 31, 11, 0, 0)

    assert es_asignacion_vigente(_asignacion(vence_en=ingenua), AHORA) is False


# ---------------------------------------------------------------------------
# Historial vía HTTP (PostgreSQL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_historial_devuelve_revocadas_y_vigentes_ordenado(contexto_auth) -> None:
    _, token = await crear_admin_prueba(contexto_auth, "admin-historial@taller.test")
    usuario = await crear_usuario_prueba(contexto_auth, "historial@taller.test")

    revocada = await crear_asignacion_prueba(
        contexto_auth,
        usuario.id,
        "MECANICO",
        desde=AHORA - timedelta(days=10),
        revocada_en=AHORA - timedelta(days=5),
    )
    vigente = await crear_asignacion_prueba(
        contexto_auth,
        usuario.id,
        "RECEPCION",
        desde=AHORA - timedelta(days=1),
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.get(f"/usuarios/{usuario.id}/roles")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario_id"] == usuario.id
    assert [a["rol"] for a in cuerpo["asignaciones"]] == ["RECEPCION", "MECANICO"]
    assert [a["vigente"] for a in cuerpo["asignaciones"]] == [True, False]
    assert cuerpo["asignaciones"][0]["id"] == vigente.id
    assert cuerpo["asignaciones"][1]["id"] == revocada.id
    assert cuerpo["asignaciones"][1]["revocada_en"] is not None


@pytest.mark.asyncio
async def test_historial_de_asignacion_vencida_no_la_marca_vigente(contexto_auth) -> None:
    _, token = await crear_admin_prueba(
        contexto_auth, "admin-historial-vencida@taller.test"
    )
    usuario = await crear_usuario_prueba(contexto_auth, "vencida@taller.test")
    await crear_asignacion_prueba(
        contexto_auth,
        usuario.id,
        "MECANICO",
        desde=AHORA - timedelta(days=2),
        vence_en=AHORA - timedelta(days=1),
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.get(f"/usuarios/{usuario.id}/roles")

    assert respuesta.status_code == 200
    asignaciones = respuesta.json()["asignaciones"]
    assert len(asignaciones) == 1
    assert asignaciones[0]["vigente"] is False
    assert asignaciones[0]["revocada_en"] is None


@pytest.mark.asyncio
async def test_historial_de_usuario_sin_asignaciones_es_vacio(contexto_auth) -> None:
    _, token = await crear_admin_prueba(
        contexto_auth, "admin-historial-vacio@taller.test"
    )
    usuario = await crear_usuario_prueba(contexto_auth, "sin-roles-historial@taller.test")

    async with cliente_http(token) as cliente:
        respuesta = await cliente.get(f"/usuarios/{usuario.id}/roles")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": usuario.id, "asignaciones": []}


@pytest.mark.asyncio
async def test_historial_de_usuario_inexistente_devuelve_404(contexto_auth) -> None:
    _, token = await crear_admin_prueba(
        contexto_auth, "admin-historial-404@taller.test"
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.get("/usuarios/999999/roles")

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "detail": "Usuario no encontrado",
        "codigo": "USUARIO_NO_ENCONTRADO",
    }


@pytest.mark.asyncio
async def test_historial_no_navega_relaciones_por_lazy_raise(contexto_auth) -> None:
    """Regla dura #3: la consulta es plana sobre `asignacion_rol`."""
    _, token = await crear_admin_prueba(
        contexto_auth, "admin-historial-plano@taller.test"
    )
    usuario = await crear_usuario_prueba(contexto_auth, "plano@taller.test")
    await crear_asignacion_prueba(
        contexto_auth, usuario.id, "MECANICO", otorgada_por=usuario.id
    )

    async with cliente_http(token) as cliente:
        respuesta = await cliente.get(f"/usuarios/{usuario.id}/roles")

    assert respuesta.status_code == 200
    asignacion = respuesta.json()["asignaciones"][0]
    assert asignacion["otorgada_por"] == usuario.id
    assert set(asignacion) == {
        "id",
        "rol",
        "desde",
        "vence_en",
        "revocada_en",
        "otorgada_por",
        "vigente",
    }

    filas = (
        await contexto_auth.execute(
            select(AsignacionRol).where(AsignacionRol.usuario_id == usuario.id)
        )
    ).scalars().all()
    assert len(filas) == 1
