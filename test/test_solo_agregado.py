"""
Tests de protección de tablas de solo-agregado (RN-15).
Verifica que los triggers BEFORE UPDATE OR DELETE bloquean modificaciones
en historial_estado_orden, movimiento_stock e historial_precio_repuesto.
Tests contra PostgreSQL real — nunca SQLite.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")


# ---------------------------------------------------------------------------
# Helpers para insertar filas mínimas que satisfagan las FKs
# ---------------------------------------------------------------------------

async def _crear_usuario(session, email: str):
    from app.modules.usuarios.models import Usuario

    u = Usuario(email=email, nombre="Test", password_hash="hash", activo=True, debe_cambiar_password=False)
    session.add(u)
    await session.flush()
    return u


async def _crear_repuesto(session, codigo: str):
    from app.modules.repuestos.models import Repuesto

    r = Repuesto(codigo=codigo, descripcion="D", precio=Decimal("50"), stock=10)
    session.add(r)
    await session.flush()
    return r


async def _crear_estado(session, codigo: str, posicion: int):
    from app.modules.ordenes.models import EstadoOrden

    e = EstadoOrden(codigo=codigo, descripcion=codigo, posicion=posicion, es_final=False)
    session.add(e)
    await session.flush()
    return e


async def _crear_cliente_vehiculo(session):
    from app.modules.clientes.models import Cliente, Vehiculo

    c = Cliente(nombre="C", documento=f"DOC{id(session)}", telefono="0")
    session.add(c)
    await session.flush()

    v = Vehiculo(cliente_id=c.id, patente=f"SA{id(session) % 9999:04d}", marca="M", modelo="X", anio=2000)
    session.add(v)
    await session.flush()
    return v


async def _crear_orden(session, vehiculo_id: int, estado: str):
    from app.modules.ordenes.models import OrdenTrabajo

    o = OrdenTrabajo(vehiculo_id=vehiculo_id, estado=estado, falla="F", creada_en=datetime.now(timezone.utc), total=Decimal("0"))
    session.add(o)
    await session.flush()
    return o


# ---------------------------------------------------------------------------
# historial_estado_orden — UPDATE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historial_estado_orden_update_bloqueado(test_db_session):
    """Trigger bloquea UPDATE en historial_estado_orden."""
    session = test_db_session

    u = await _crear_usuario(session, "heo_upd@test.com")
    est = await _crear_estado(session, "HEO_UPD", 901)
    v = await _crear_cliente_vehiculo(session)
    o = await _crear_orden(session, v.id, "HEO_UPD")

    from app.modules.ordenes.models import HistorialEstadoOrden

    h = HistorialEstadoOrden(
        orden_id=o.id,
        hasta_estado="HEO_UPD",
        usuario_id=u.id,
        cuando=datetime.now(timezone.utc),
    )
    session.add(h)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("UPDATE historial_estado_orden SET cuando = NOW() WHERE id = :id"),
            {"id": h.id},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# historial_estado_orden — DELETE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historial_estado_orden_delete_bloqueado(test_db_session):
    """Trigger bloquea DELETE en historial_estado_orden."""
    session = test_db_session

    u = await _crear_usuario(session, "heo_del@test.com")
    est = await _crear_estado(session, "HEO_DEL", 902)
    v = await _crear_cliente_vehiculo(session)
    o = await _crear_orden(session, v.id, "HEO_DEL")

    from app.modules.ordenes.models import HistorialEstadoOrden

    h = HistorialEstadoOrden(
        orden_id=o.id,
        hasta_estado="HEO_DEL",
        usuario_id=u.id,
        cuando=datetime.now(timezone.utc),
    )
    session.add(h)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("DELETE FROM historial_estado_orden WHERE id = :id"),
            {"id": h.id},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# movimiento_stock — UPDATE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_movimiento_stock_update_bloqueado(test_db_session):
    """Trigger bloquea UPDATE en movimiento_stock."""
    session = test_db_session

    u = await _crear_usuario(session, "ms_upd@test.com")
    r = await _crear_repuesto(session, "MS_UPD")

    from app.modules.repuestos.models import MovimientoStock

    m = MovimientoStock(repuesto_id=r.id, usuario_id=u.id, cantidad=5, motivo="ALTA", cuando=datetime.now(timezone.utc))
    session.add(m)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("UPDATE movimiento_stock SET cantidad = 999 WHERE id = :id"),
            {"id": m.id},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# movimiento_stock — DELETE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_movimiento_stock_delete_bloqueado(test_db_session):
    """Trigger bloquea DELETE en movimiento_stock."""
    session = test_db_session

    u = await _crear_usuario(session, "ms_del@test.com")
    r = await _crear_repuesto(session, "MS_DEL")

    from app.modules.repuestos.models import MovimientoStock

    m = MovimientoStock(repuesto_id=r.id, usuario_id=u.id, cantidad=3, motivo="REPOSICION", cuando=datetime.now(timezone.utc))
    session.add(m)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("DELETE FROM movimiento_stock WHERE id = :id"),
            {"id": m.id},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# historial_precio_repuesto — UPDATE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historial_precio_update_bloqueado(test_db_session):
    """Trigger bloquea UPDATE en historial_precio_repuesto."""
    session = test_db_session

    u = await _crear_usuario(session, "hpr_upd@test.com")
    r = await _crear_repuesto(session, "HPR_UPD")

    from app.modules.repuestos.models import HistorialPrecioRepuesto

    h = HistorialPrecioRepuesto(
        repuesto_id=r.id,
        usuario_id=u.id,
        precio_anterior=Decimal("50"),
        precio_nuevo=Decimal("75"),
        cuando=datetime.now(timezone.utc),
    )
    session.add(h)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("UPDATE historial_precio_repuesto SET precio_nuevo = 1000 WHERE id = :id"),
            {"id": h.id},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# historial_precio_repuesto — DELETE bloqueado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historial_precio_delete_bloqueado(test_db_session):
    """Trigger bloquea DELETE en historial_precio_repuesto."""
    session = test_db_session

    u = await _crear_usuario(session, "hpr_del@test.com")
    r = await _crear_repuesto(session, "HPR_DEL")

    from app.modules.repuestos.models import HistorialPrecioRepuesto

    h = HistorialPrecioRepuesto(
        repuesto_id=r.id,
        usuario_id=u.id,
        precio_anterior=Decimal("50"),
        precio_nuevo=Decimal("80"),
        cuando=datetime.now(timezone.utc),
    )
    session.add(h)
    await session.flush()

    with pytest.raises((ProgrammingError, Exception), match="solo-agregado|bloquear"):
        await session.execute(
            text("DELETE FROM historial_precio_repuesto WHERE id = :id"),
            {"id": h.id},
        )
        await session.flush()
