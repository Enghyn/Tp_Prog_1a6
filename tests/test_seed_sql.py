import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import func, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# La configuración exige JWT_SECRET incluso para importar el módulo.
os.environ.setdefault("JWT_SECRET", "clave-secreta-de-prueba")

import seed
from app.core.configuracion import configuracion
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
from app.modules.repuestos.models import MovimientoStock, Repuesto
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario


RUTA_SQL = Path(__file__).resolve().parent.parent / "test" / "seed.sql"
DB_URL = os.getenv("TEST_DATABASE_URL", str(configuracion.database_url))

TABLAS = {
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

CONTEOS_ESPERADOS = {
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


@asynccontextmanager
async def transaccion_aislada():
    """Conexión con transacción externa y rollback, para no ensuciar la base.

    Solo se omite el test si la base no está disponible. Un error del script
    SQL o de una aserción debe fallar, nunca convertirse en SKIP.
    """
    engine = create_async_engine(DB_URL, poolclass=NullPool)
    try:
        connection = await engine.connect()
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Base de datos PostgreSQL no disponible o no accesible: {exc}")

    try:
        trans = await connection.begin()
        # SQLAlchemy difiere el BEGIN hasta la primera sentencia. Forzarlo
        # evita que el script crudo de asyncpg se ejecute en autocommit.
        await connection.exec_driver_sql("SELECT 1")
    except Exception as exc:
        await connection.close()
        await engine.dispose()
        pytest.skip(f"Base de datos PostgreSQL no disponible o no accesible: {exc}")

    try:
        yield connection
    finally:
        await trans.rollback()
        await connection.close()
        await engine.dispose()


def _sin_control_transaccional(script: str) -> str:
    """Quita BEGIN/COMMIT para ejecutar dentro de la transacción del test."""
    return "\n".join(
        linea
        for linea in script.splitlines()
        if linea.strip().upper() not in {"BEGIN;", "COMMIT;"}
    )


async def _ejecutar_sql(connection, script: str) -> None:
    raw = (await connection.get_raw_connection()).driver_connection
    await raw.execute(_sin_control_transaccional(script))


async def _conteos(connection) -> dict[str, int]:
    return {
        nombre: (
            await connection.execute(
                sa_select(func.count()).select_from(modelo)
            )
        ).scalar_one()
        for nombre, modelo in TABLAS.items()
    }


async def _claves_naturales(connection) -> dict[str, set[tuple]]:
    async def filas(consulta):
        return {tuple(fila) for fila in (await connection.execute(consulta)).all()}

    return {
        "estado_orden": await filas(sa_select(EstadoOrden.codigo)),
        "usuario": await filas(sa_select(Usuario.email)),
        "asignacion_rol": await filas(
            sa_select(Usuario.email, AsignacionRol.rol)
            .join(Usuario, AsignacionRol.usuario_id == Usuario.id)
            .where(AsignacionRol.revocada_en.is_(None))
        ),
        "cliente": await filas(sa_select(Cliente.documento)),
        "vehiculo": await filas(
            sa_select(Vehiculo.patente).where(Vehiculo.borrado_en.is_(None))
        ),
        "repuesto": await filas(
            sa_select(Repuesto.codigo).where(Repuesto.borrado_en.is_(None))
        ),
        "orden_trabajo": await filas(
            sa_select(
                OrdenTrabajo.falla,
                Vehiculo.patente,
                OrdenTrabajo.estado,
                OrdenTrabajo.total,
            ).join(Vehiculo, OrdenTrabajo.vehiculo_id == Vehiculo.id)
        ),
        "item_orden": await filas(
            sa_select(
                OrdenTrabajo.falla,
                Repuesto.codigo,
                ItemOrden.cantidad,
                ItemOrden.precio_unitario,
            )
            .join(OrdenTrabajo, ItemOrden.orden_id == OrdenTrabajo.id)
            .join(Repuesto, ItemOrden.repuesto_id == Repuesto.id)
        ),
        "historial_estado_orden": await filas(
            sa_select(
                OrdenTrabajo.falla,
                HistorialEstadoOrden.desde_estado,
                HistorialEstadoOrden.hasta_estado,
                HistorialEstadoOrden.cuando,
            ).join(OrdenTrabajo, HistorialEstadoOrden.orden_id == OrdenTrabajo.id)
        ),
        "movimiento_stock": await filas(
            sa_select(
                Repuesto.codigo,
                MovimientoStock.motivo,
                MovimientoStock.cantidad,
                MovimientoStock.cuando,
            ).join(Repuesto, MovimientoStock.repuesto_id == Repuesto.id)
        ),
        "evento_seguridad": await filas(
            sa_select(EventoSeguridad.actor, EventoSeguridad.accion)
        ),
    }


@pytest.mark.asyncio
async def test_seed_sql_doble_carga_es_idempotente():
    script = RUTA_SQL.read_text(encoding="utf-8")

    async with transaccion_aislada() as connection:
        await _ejecutar_sql(connection, script)
        primero = await _conteos(connection)
        await _ejecutar_sql(connection, script)
        segundo = await _conteos(connection)

    assert primero == segundo == CONTEOS_ESPERADOS


@pytest.mark.asyncio
async def test_paridad_entre_seed_py_y_seed_sql():
    script = RUTA_SQL.read_text(encoding="utf-8")

    async with transaccion_aislada() as connection:
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        await seed.ejecutar_seed(session_factory)
        conteos_py = await _conteos(connection)
        claves_py = await _claves_naturales(connection)

    async with transaccion_aislada() as connection:
        await _ejecutar_sql(connection, script)
        await _ejecutar_sql(connection, script)
        conteos_sql = await _conteos(connection)
        claves_sql = await _claves_naturales(connection)

    assert conteos_py == conteos_sql == CONTEOS_ESPERADOS
    assert claves_py == claves_sql
