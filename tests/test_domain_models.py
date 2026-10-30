"""
Tests para los modelos de dominio del taller (C-07).
Todos contra PostgreSQL real — nunca SQLite.
"""
import os
import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")


# ---------------------------------------------------------------------------
# Grupo 1: Cliente y Vehiculo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cliente_insercion_valida(test_db_session):
    """Inserción básica de un cliente."""
    from app.modules.clientes.models import Cliente

    session = test_db_session
    c = Cliente(nombre="Juan Pérez", documento="12345678", telefono="0351-111")
    session.add(c)
    await session.flush()
    assert c.id is not None


@pytest.mark.asyncio
async def test_vehiculo_anio_invalido_rechazado(test_db_session):
    """CHECK anio 1950-2100 — año fuera de rango debe fallar."""
    from app.modules.clientes.models import Cliente, Vehiculo

    session = test_db_session
    c = Cliente(nombre="Test", documento="DOC001", telefono="000")
    session.add(c)
    await session.flush()

    v = Vehiculo(
        cliente_id=c.id,
        patente="AA000AA",
        marca="Ford",
        modelo="Falcon",
        anio=1900,  # inválido
    )
    session.add(v)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_vehiculo_anio_valido(test_db_session):
    """Año válido dentro del rango 1950-2100."""
    from app.modules.clientes.models import Cliente, Vehiculo

    session = test_db_session
    c = Cliente(nombre="Ana", documento="DOC002", telefono="000")
    session.add(c)
    await session.flush()

    v = Vehiculo(
        cliente_id=c.id,
        patente="AB123CD",
        marca="Renault",
        modelo="Clio",
        anio=2010,
    )
    session.add(v)
    await session.flush()
    assert v.id is not None


@pytest.mark.asyncio
async def test_patente_unica_en_vigentes(test_db_session):
    """UNIQUE parcial — misma patente sin baja lógica debe fallar."""
    from app.modules.clientes.models import Cliente, Vehiculo

    session = test_db_session
    c = Cliente(nombre="Bob", documento="DOC003", telefono="000")
    session.add(c)
    await session.flush()

    v1 = Vehiculo(cliente_id=c.id, patente="ZZ999ZZ", marca="X", modelo="Y", anio=2000)
    session.add(v1)
    await session.flush()

    v2 = Vehiculo(cliente_id=c.id, patente="ZZ999ZZ", marca="X2", modelo="Y2", anio=2001)
    session.add(v2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_patente_reutilizable_tras_baja_logica(test_db_session):
    """Índice parcial WHERE borrado_en IS NULL — patente libre tras baja."""
    from app.modules.clientes.models import Cliente, Vehiculo

    session = test_db_session
    c = Cliente(nombre="Eve", documento="DOC004", telefono="000")
    session.add(c)
    await session.flush()

    v1 = Vehiculo(cliente_id=c.id, patente="TT777TT", marca="X", modelo="Y", anio=2000)
    session.add(v1)
    await session.flush()

    # baja lógica
    v1.borrado_en = datetime.now(timezone.utc)
    await session.flush()

    # misma patente ahora permitida
    v2 = Vehiculo(cliente_id=c.id, patente="TT777TT", marca="X2", modelo="Y2", anio=2001)
    session.add(v2)
    await session.flush()
    assert v2.id is not None


# ---------------------------------------------------------------------------
# Grupo 2: Repuesto, MovimientoStock, HistorialPrecioRepuesto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repuesto_precio_cero_rechazado(test_db_session):
    """CHECK precio > 0."""
    from app.modules.repuestos.models import Repuesto
    from decimal import Decimal

    session = test_db_session
    r = Repuesto(codigo="REP001", descripcion="Bujía", precio=Decimal("0"), stock=10)
    session.add(r)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_repuesto_precio_positivo_valido(test_db_session):
    """Precio > 0 aceptado."""
    from app.modules.repuestos.models import Repuesto
    from decimal import Decimal

    session = test_db_session
    r = Repuesto(codigo="REP002", descripcion="Filtro", precio=Decimal("150.50"), stock=5)
    session.add(r)
    await session.flush()
    assert r.id is not None


@pytest.mark.asyncio
async def test_repuesto_stock_negativo_rechazado(test_db_session):
    """CHECK stock >= 0."""
    from app.modules.repuestos.models import Repuesto
    from decimal import Decimal

    session = test_db_session
    r = Repuesto(codigo="REP003", descripcion="Aceite", precio=Decimal("200"), stock=-1)
    session.add(r)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_repuesto_codigo_unico_vigente(test_db_session):
    """Índice parcial — código duplicado sin baja lógica debe fallar."""
    from app.modules.repuestos.models import Repuesto
    from decimal import Decimal

    session = test_db_session
    r1 = Repuesto(codigo="DUPCODE", descripcion="A", precio=Decimal("10"), stock=1)
    session.add(r1)
    await session.flush()

    r2 = Repuesto(codigo="DUPCODE", descripcion="B", precio=Decimal("20"), stock=2)
    session.add(r2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_repuesto_codigo_reutilizable_tras_baja(test_db_session):
    """Código libre tras baja lógica."""
    from app.modules.repuestos.models import Repuesto
    from decimal import Decimal

    session = test_db_session
    r1 = Repuesto(codigo="OLDCODE", descripcion="A", precio=Decimal("10"), stock=1)
    session.add(r1)
    await session.flush()

    r1.borrado_en = datetime.now(timezone.utc)
    await session.flush()

    r2 = Repuesto(codigo="OLDCODE", descripcion="Nuevo", precio=Decimal("20"), stock=2)
    session.add(r2)
    await session.flush()
    assert r2.id is not None


@pytest.mark.asyncio
async def test_movimiento_stock_cantidad_cero_rechazado(test_db_session):
    """CHECK cantidad != 0."""
    from app.modules.clientes.models import Cliente
    from app.modules.repuestos.models import Repuesto, MovimientoStock
    from app.modules.usuarios.models import Usuario
    from decimal import Decimal

    session = test_db_session

    u = Usuario(email="mov@test.com", nombre="Mov", password_hash="h", activo=True, debe_cambiar_password=False)
    session.add(u)
    await session.flush()

    r = Repuesto(codigo="MOV_REP", descripcion="X", precio=Decimal("10"), stock=5)
    session.add(r)
    await session.flush()

    m = MovimientoStock(repuesto_id=r.id, usuario_id=u.id, cantidad=0, motivo="ALTA", cuando=datetime.now(timezone.utc))
    session.add(m)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_historial_precio_check_precio_nuevo_mayor(test_db_session):
    """CHECK precio_nuevo > precio_anterior."""
    from app.modules.repuestos.models import Repuesto, HistorialPrecioRepuesto
    from app.modules.usuarios.models import Usuario
    from decimal import Decimal

    session = test_db_session

    u = Usuario(email="hist@test.com", nombre="Hist", password_hash="h", activo=True, debe_cambiar_password=False)
    session.add(u)
    await session.flush()

    r = Repuesto(codigo="HIST_REP", descripcion="Y", precio=Decimal("100"), stock=3)
    session.add(r)
    await session.flush()

    h = HistorialPrecioRepuesto(
        repuesto_id=r.id,
        usuario_id=u.id,
        precio_anterior=Decimal("100"),
        precio_nuevo=Decimal("50"),  # inválido, debe ser > anterior
        cuando=datetime.now(timezone.utc),
    )
    session.add(h)
    with pytest.raises(IntegrityError):
        await session.flush()


# ---------------------------------------------------------------------------
# Grupo 3: OrdenTrabajo, ItemOrden, HistorialEstadoOrden
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_orden_duplicado_rechazado(test_db_session):
    """UNIQUE (orden_id, repuesto_id) — ítem repetido en misma orden debe fallar."""
    from app.modules.clientes.models import Cliente, Vehiculo
    from app.modules.repuestos.models import Repuesto
    from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo, ItemOrden
    from app.modules.usuarios.models import Usuario
    from decimal import Decimal

    session = test_db_session

    u = Usuario(email="itemdup@test.com", nombre="I", password_hash="h", activo=True, debe_cambiar_password=False)
    session.add(u)
    await session.flush()

    c = Cliente(nombre="C", documento="DOCITEM", telefono="0")
    session.add(c)
    await session.flush()

    v = Vehiculo(cliente_id=c.id, patente="IT001IT", marca="M", modelo="X", anio=2000)
    session.add(v)
    await session.flush()

    r = Repuesto(codigo="IT_REP", descripcion="R", precio=Decimal("50"), stock=10)
    session.add(r)
    await session.flush()

    est = EstadoOrden(codigo="PENDIENTE", descripcion="Pendiente", posicion=1, es_final=False)
    session.add(est)
    await session.flush()

    o = OrdenTrabajo(vehiculo_id=v.id, estado="PENDIENTE", falla="Test", creada_en=datetime.now(timezone.utc), total=Decimal("0"))
    session.add(o)
    await session.flush()

    i1 = ItemOrden(orden_id=o.id, repuesto_id=r.id, cantidad=2, precio_unitario=Decimal("50"))
    session.add(i1)
    await session.flush()

    i2 = ItemOrden(orden_id=o.id, repuesto_id=r.id, cantidad=1, precio_unitario=Decimal("50"))  # duplicado
    session.add(i2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_item_orden_cantidad_cero_rechazado(test_db_session):
    """CHECK cantidad > 0."""
    from app.modules.clientes.models import Cliente, Vehiculo
    from app.modules.repuestos.models import Repuesto
    from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo, ItemOrden
    from app.modules.usuarios.models import Usuario
    from decimal import Decimal

    session = test_db_session

    u = Usuario(email="qty0@test.com", nombre="Q", password_hash="h", activo=True, debe_cambiar_password=False)
    session.add(u)
    await session.flush()

    c = Cliente(nombre="C2", documento="DOCQTY", telefono="0")
    session.add(c)
    await session.flush()

    v = Vehiculo(cliente_id=c.id, patente="QT001QT", marca="M", modelo="X", anio=2001)
    session.add(v)
    await session.flush()

    r = Repuesto(codigo="QT_REP", descripcion="R", precio=Decimal("30"), stock=5)
    session.add(r)
    await session.flush()

    est = EstadoOrden(codigo="PEND2", descripcion="Pendiente2", posicion=10, es_final=False)
    session.add(est)
    await session.flush()

    o = OrdenTrabajo(vehiculo_id=v.id, estado="PEND2", falla="Test", creada_en=datetime.now(timezone.utc), total=Decimal("0"))
    session.add(o)
    await session.flush()

    i = ItemOrden(orden_id=o.id, repuesto_id=r.id, cantidad=0, precio_unitario=Decimal("30"))
    session.add(i)
    with pytest.raises(IntegrityError):
        await session.flush()
