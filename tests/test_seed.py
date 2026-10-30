import os
from datetime import datetime, timezone
from decimal import Decimal

import bcrypt
import pytest
from sqlalchemy import func, select as sa_select

# La configuración exige JWT_SECRET incluso para importar el módulo.
os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

import seed
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
from app.modules.repuestos.models import MovimientoStock, Repuesto
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario


def test_catalogo_declarado_es_canonico():
    """Verifica los datos canónicos sin depender de PostgreSQL."""
    assert [
        (estado.codigo, estado.posicion, estado.es_final)
        for estado in seed.ESTADOS_ORDEN
    ] == [
        ("PENDIENTE", 1, False),
        ("EN_REPARACION", 2, False),
        ("TERMINADA", 3, True),
        ("CANCELADA", 4, True),
    ]


@pytest.mark.asyncio
async def test_seed_carga_catalogo_completo(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        filas = (
            await session.execute(
                sa_select(EstadoOrden).order_by(EstadoOrden.posicion)
            )
        ).scalars().all()

    assert [
        (fila.codigo, fila.posicion, fila.es_final) for fila in filas
    ] == [
        ("PENDIENTE", 1, False),
        ("EN_REPARACION", 2, False),
        ("TERMINADA", 3, True),
        ("CANCELADA", 4, True),
    ]


@pytest.mark.asyncio
async def test_seed_repite_catalogo_sin_duplicar(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        total = (
            await session.execute(
                sa_select(func.count()).select_from(EstadoOrden)
            )
        ).scalar_one()

    assert total == 4


@pytest.mark.asyncio
async def test_seed_converge_catalogo_alterado(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        async with session.begin():
            estado = (
                await session.execute(
                    sa_select(EstadoOrden).where(
                        EstadoOrden.codigo == "TERMINADA"
                    )
                )
            ).scalar_one()
            estado.descripcion = "alterado"
            estado.posicion = 99
            estado.es_final = False
            session.add(estado)

    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        estado = (
            await session.execute(
                sa_select(EstadoOrden).where(EstadoOrden.codigo == "TERMINADA")
            )
        ).scalar_one()

    assert (estado.descripcion, estado.posicion, estado.es_final) == (
        "Terminada",
        3,
        True,
    )

def test_usuarios_declarados_cubren_los_cuatro_roles():
    assert {usuario.rol for usuario in seed.USUARIOS} == {
        "ADMIN",
        "RECEPCION",
        "MECANICO",
        "CLIENTE",
    }
    assert len({usuario.email for usuario in seed.USUARIOS}) == 4
    assert sum(usuario.debe_cambiar_password for usuario in seed.USUARIOS) >= 1


@pytest.mark.asyncio
async def test_seed_crea_usuarios_y_roles(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        usuarios = (
            await session.execute(sa_select(Usuario).order_by(Usuario.id))
        ).scalars().all()
        roles = (
            await session.execute(
                sa_select(AsignacionRol).where(AsignacionRol.revocada_en.is_(None))
            )
        ).scalars().all()

    assert len(usuarios) == 4
    por_email = {usuario.email: usuario for usuario in usuarios}
    admin = por_email["admin@taller.local"]

    for esperado in seed.USUARIOS:
        usuario = por_email[esperado.email]
        assert bcrypt.checkpw(
            esperado.password.encode("utf-8"),
            usuario.password_hash.encode("utf-8"),
        )
        abiertos = [
            rol
            for rol in roles
            if rol.usuario_id == usuario.id and rol.revocada_en is None
        ]
        assert [rol.rol for rol in abiertos] == [esperado.rol]
        if esperado.rol != "ADMIN":
            assert abiertos[0].otorgada_por == admin.id

    assert any(usuario.debe_cambiar_password for usuario in usuarios)


@pytest.mark.asyncio
async def test_seed_no_sobrescribe_password_ni_duplica_rol(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        async with session.begin():
            usuario = (
                await session.execute(
                    sa_select(Usuario).where(Usuario.email == "admin@taller.local")
                )
            ).scalar_one()
            usuario.password_hash = "hash-personalizado"
            session.add(usuario)

    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        usuario = (
            await session.execute(
                sa_select(Usuario).where(Usuario.email == "admin@taller.local")
            )
        ).scalar_one()
        total_roles = (
            await session.execute(
                sa_select(func.count())
                .select_from(AsignacionRol)
                .where(AsignacionRol.usuario_id == usuario.id)
            )
        ).scalar_one()

    assert usuario.password_hash == "hash-personalizado"
    assert total_roles == 1

def test_repuestos_declarados_tienen_stock_positivo():
    assert [repuesto.codigo for repuesto in seed.REPUESTOS] == [
        "FIL-001",
        "ACE-001",
        "BAT-001",
        "PAS-001",
    ]
    assert all(repuesto.stock > 0 for repuesto in seed.REPUESTOS)
    assert all(repuesto.precio > 0 for repuesto in seed.REPUESTOS)


@pytest.mark.asyncio
async def test_seed_carga_repuestos_y_movimientos_alta(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        repuestos = (
            await session.execute(sa_select(Repuesto).order_by(Repuesto.codigo))
        ).scalars().all()
        movimientos = (
            await session.execute(
                sa_select(MovimientoStock).where(
                    MovimientoStock.motivo == "ALTA"
                )
            )
        ).scalars().all()

    assert [repuesto.codigo for repuesto in repuestos] == [
        "ACE-001",
        "BAT-001",
        "FIL-001",
        "PAS-001",
    ]
    esperados = {repuesto.codigo: repuesto for repuesto in seed.REPUESTOS}
    for repuesto in repuestos:
        esperado = esperados[repuesto.codigo]
        assert repuesto.stock == esperado.stock
        altas = [
            movimiento
            for movimiento in movimientos
            if movimiento.repuesto_id == repuesto.id
        ]
        assert len(altas) == 1
        assert altas[0].cantidad == esperado.stock + esperado.consumo_terminacion


@pytest.mark.asyncio
async def test_seed_mantiene_stock_igual_a_suma_de_movimientos(
    seed_session_factory,
):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        repuestos = (
            await session.execute(sa_select(Repuesto))
        ).scalars().all()
        for repuesto in repuestos:
            total = (
                await session.execute(
                    sa_select(func.coalesce(func.sum(MovimientoStock.cantidad), 0))
                    .where(MovimientoStock.repuesto_id == repuesto.id)
                )
            ).scalar_one()
            assert total == repuesto.stock


@pytest.mark.asyncio
async def test_seed_no_reinicia_stock_ni_duplica_alta(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        async with session.begin():
            repuesto = (
                await session.execute(
                    sa_select(Repuesto).where(Repuesto.codigo == "FIL-001")
                )
            ).scalar_one()
            admin = (
                await session.execute(
                    sa_select(Usuario).where(
                        Usuario.email == "admin@taller.local"
                    )
                )
            ).scalar_one()
            repuesto.stock = 999
            session.add(repuesto)
            session.add(
                MovimientoStock(
                    repuesto_id=repuesto.id,
                    orden_id=None,
                    usuario_id=admin.id,
                    cantidad=989,
                    motivo="ALTA",
                    cuando=datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc),
                )
            )

    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        repuesto = (
            await session.execute(
                sa_select(Repuesto).where(Repuesto.codigo == "FIL-001")
            )
        ).scalar_one()
        altas = (
            await session.execute(
                sa_select(func.count())
                .select_from(MovimientoStock)
                .where(
                    MovimientoStock.repuesto_id == repuesto.id,
                    MovimientoStock.motivo == "ALTA",
                )
            )
        ).scalar_one()
        total = (
            await session.execute(
                sa_select(func.sum(MovimientoStock.cantidad)).where(
                    MovimientoStock.repuesto_id == repuesto.id
                )
            )
        ).scalar_one()

    assert repuesto.stock == 999
    assert altas == 2
    assert total == repuesto.stock

def test_datos_demo_declarados_son_coherentes():
    assert len(seed.CLIENTES) == 2
    assert len(seed.VEHICULOS) == 3
    assert {orden.estado for orden in seed.ORDENES} == {
        "PENDIENTE",
        "EN_REPARACION",
        "TERMINADA",
    }
    assert all(orden.items for orden in seed.ORDENES)


@pytest.mark.asyncio
async def test_seed_carga_clientes_y_vehiculos(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        clientes = (
            await session.execute(sa_select(Cliente).order_by(Cliente.documento))
        ).scalars().all()
        vehiculos = (
            await session.execute(sa_select(Vehiculo).order_by(Vehiculo.patente))
        ).scalars().all()
        usuario_cliente = (
            await session.execute(
                sa_select(Usuario).where(
                    Usuario.email == "cliente@taller.local"
                )
            )
        ).scalar_one()

    assert len(clientes) == 2
    assert len(vehiculos) == 3
    cliente_uno = next(
        cliente for cliente in clientes if cliente.documento == "30111222"
    )
    assert cliente_uno.usuario_id == usuario_cliente.id
    assert [
        vehiculo.patente
        for vehiculo in vehiculos
        if vehiculo.cliente_id == cliente_uno.id
    ] == ["AB123CD", "AC456EF"]


@pytest.mark.asyncio
async def test_seed_carga_ordenes_con_totales_e_items(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        ordenes = (
            await session.execute(sa_select(OrdenTrabajo).order_by(OrdenTrabajo.id))
        ).scalars().all()

        assert len(ordenes) == 3
        assert {orden.estado for orden in ordenes} == {
            "PENDIENTE",
            "EN_REPARACION",
            "TERMINADA",
        }

        for orden in ordenes:
            items = (
                await session.execute(
                    sa_select(ItemOrden).where(ItemOrden.orden_id == orden.id)
                )
            ).scalars().all()
            assert items
            total = sum(
                (item.precio_unitario * item.cantidad for item in items),
                Decimal("0.00"),
            )
            assert orden.total == total


@pytest.mark.asyncio
async def test_seed_historial_parte_de_nulo_y_no_tiene_saltos(
    seed_session_factory,
):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        ordenes = (
            await session.execute(sa_select(OrdenTrabajo))
        ).scalars().all()

        for orden in ordenes:
            historial = (
                await session.execute(
                    sa_select(HistorialEstadoOrden)
                    .where(HistorialEstadoOrden.orden_id == orden.id)
                    .order_by(HistorialEstadoOrden.cuando)
                )
            ).scalars().all()
            assert historial
            assert historial[0].desde_estado is None
            assert historial[-1].hasta_estado == orden.estado
            for anterior, siguiente in zip(historial, historial[1:]):
                assert anterior.hasta_estado == siguiente.desde_estado


@pytest.mark.asyncio
async def test_seed_termina_bat_y_mantiene_stock(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        repuesto = (
            await session.execute(
                sa_select(Repuesto).where(Repuesto.codigo == "BAT-001")
            )
        ).scalar_one()
        orden = (
            await session.execute(
                sa_select(OrdenTrabajo).where(
                    OrdenTrabajo.estado == "TERMINADA"
                )
            )
        ).scalar_one()
        movimientos = (
            await session.execute(
                sa_select(MovimientoStock).where(
                    MovimientoStock.repuesto_id == repuesto.id
                )
            )
        ).scalars().all()

    terminacion = [
        movimiento
        for movimiento in movimientos
        if movimiento.motivo == "TERMINACION"
    ]
    assert len(terminacion) == 1
    assert terminacion[0].cantidad == -1
    assert terminacion[0].orden_id == orden.id
    assert sum(movimiento.cantidad for movimiento in movimientos) == repuesto.stock


@pytest.mark.asyncio
async def test_seed_doble_ejecucion_no_duplica_ordenes(seed_session_factory):
    async def conteos():
        async with seed_session_factory() as session:
            return {
                "ordenes": (
                    await session.execute(
                        sa_select(func.count()).select_from(OrdenTrabajo)
                    )
                ).scalar_one(),
                "items": (
                    await session.execute(
                        sa_select(func.count()).select_from(ItemOrden)
                    )
                ).scalar_one(),
                "historial": (
                    await session.execute(
                        sa_select(func.count()).select_from(HistorialEstadoOrden)
                    )
                ).scalar_one(),
            }

    await seed.ejecutar_seed(seed_session_factory)
    primero = await conteos()
    await seed.ejecutar_seed(seed_session_factory)
    segundo = await conteos()

    assert primero == segundo == {"ordenes": 3, "items": 4, "historial": 6}

@pytest.mark.asyncio
async def test_seed_registra_evento_sistema_una_sola_vez(seed_session_factory):
    await seed.ejecutar_seed(seed_session_factory)
    await seed.ejecutar_seed(seed_session_factory)

    async with seed_session_factory() as session:
        eventos = (
            await session.execute(
                sa_select(EventoSeguridad).where(
                    EventoSeguridad.actor == "SISTEMA",
                    EventoSeguridad.accion == "seed_inicial",
                )
            )
        ).scalars().all()

    assert len(eventos) == 1


@pytest.mark.asyncio
async def test_seed_doble_ejecucion_no_altera_ningun_conteo(seed_session_factory):
    tablas = {
        "estado_orden": EstadoOrden,
        "usuario": Usuario,
        "asignacion_rol": AsignacionRol,
        "repuesto": Repuesto,
        "movimiento_stock": MovimientoStock,
        "cliente": Cliente,
        "vehiculo": Vehiculo,
        "orden_trabajo": OrdenTrabajo,
        "item_orden": ItemOrden,
        "historial_estado_orden": HistorialEstadoOrden,
        "evento_seguridad": EventoSeguridad,
    }

    async def snapshot():
        async with seed_session_factory() as session:
            return {
                nombre: (
                    await session.execute(
                        sa_select(func.count()).select_from(modelo)
                    )
                ).scalar_one()
                for nombre, modelo in tablas.items()
            }

    await seed.ejecutar_seed(seed_session_factory)
    primero = await snapshot()
    await seed.ejecutar_seed(seed_session_factory)
    segundo = await snapshot()

    assert primero == segundo
    assert primero == {
        "estado_orden": 4,
        "usuario": 4,
        "asignacion_rol": 4,
        "repuesto": 4,
        "movimiento_stock": 5,
        "cliente": 2,
        "vehiculo": 3,
        "orden_trabajo": 3,
        "item_orden": 4,
        "historial_estado_orden": 6,
        "evento_seguridad": 1,
    }


def test_reset_sin_confirmacion_aborta_antes_de_escribir(monkeypatch):
    llamado = {"reset": False}

    def reset_espia():
        llamado["reset"] = True

    monkeypatch.setattr(seed, "_reset_esquema", reset_espia)

    assert seed.main(["--reset"]) == 2
    assert llamado["reset"] is False


def test_entorno_produccion_aborta_sin_forzar(monkeypatch):
    monkeypatch.setattr(seed.configuracion, "entorno", "produccion")

    assert seed.main([]) == 2
