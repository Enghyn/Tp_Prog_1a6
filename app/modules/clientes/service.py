from datetime import datetime, timezone

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import obtener_usuario_actual
from app.core.errors import ConflictoError, NoEncontradoError
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.clientes.schemas import ClienteCreate, ClienteRead, VehiculoCreate, VehiculoRead
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo


async def crear_cliente(uow: ClientesUnitOfWork, datos: ClienteCreate) -> Cliente:
    existente = await uow.clientes.get_all()
    for c in existente:
        if c.documento == datos.documento:
            raise ConflictoError("Documento duplicado", "DOCUMENTO_DUPLICADO")
    cliente = Cliente(nombre=datos.nombre, documento=datos.documento, telefono=datos.telefono)
    await uow.clientes.add(cliente)
    await uow.session.flush()
    stmt = select(Cliente).options(selectinload(Cliente.vehiculos)).where(Cliente.id == cliente.id)
    res = await uow.session.execute(stmt)
    return res.scalars().first()


async def obtener_cliente_con_vehiculos(uow: ClientesUnitOfWork, cliente_id: int) -> Cliente:
    stmt = (
        select(Cliente)
        .options(selectinload(Cliente.vehiculos))
        .where(Cliente.id == cliente_id)
    )
    res = await uow.session.execute(stmt)
    cliente = res.scalars().first()
    if cliente is None:
        raise NoEncontradoError("Cliente no encontrado", "CLIENTE_NO_ENCONTRADO")
    return cliente


async def crear_vehiculo(uow: ClientesUnitOfWork, cliente_id: int, datos: VehiculoCreate) -> Vehiculo:
    cliente = await uow.clientes.get_by_id(cliente_id)
    if cliente is None:
        raise NoEncontradoError("Cliente no encontrado", "CLIENTE_NO_ENCONTRADO")
    # patente vigente duplicada
    stmt = select(Vehiculo).where(Vehiculo.patente == datos.patente, Vehiculo.borrado_en.is_(None))
    res = await uow.session.execute(stmt)
    if res.scalars().first() is not None:
        raise ConflictoError("Patente duplicada", "PATENTE_DUPLICADA")
    vehiculo = Vehiculo(cliente_id=cliente_id, patente=datos.patente, marca=datos.marca, modelo=datos.modelo, anio=datos.anio)
    await uow.vehiculos.add(vehiculo)
    return vehiculo


async def baja_vehiculo(uow: ClientesUnitOfWork, vehiculo_id: int) -> None:
    vehiculo = await uow.vehiculos.get_by_id(vehiculo_id)
    if vehiculo is None:
        raise NoEncontradoError("Vehículo no encontrado", "VEHICULO_NO_ENCONTRADO")
    # RN-16: órdenes abiertas
    stmt = select(
        exists(
            select(OrdenTrabajo.id)
            .join(EstadoOrden, EstadoOrden.codigo == OrdenTrabajo.estado)
            .where(OrdenTrabajo.vehiculo_id == vehiculo_id, EstadoOrden.es_final.is_(False))
        )
    )
    res = await uow.session.execute(stmt)
    if bool(res.scalar()):
        raise ConflictoError("Vehículo con órdenes abiertas", "VEHICULO_CON_ORDENES_ABIERTAS")
    await uow.vehiculos.soft_delete(vehiculo)


async def mis_vehiculos(uow: ClientesUnitOfWork, usuario_id: int) -> list[Vehiculo]:
    stmt = select(Cliente).where(Cliente.usuario_id == usuario_id)
    res = await uow.session.execute(stmt)
    cliente = res.scalars().first()
    if cliente is None:
        raise NoEncontradoError("Cliente no vinculado", "CLIENTE_NO_VINCULADO")
    stmt2 = select(Vehiculo).where(Vehiculo.cliente_id == cliente.id, Vehiculo.borrado_en.is_(None))
    res2 = await uow.session.execute(stmt2)
    return list(res2.scalars().all())