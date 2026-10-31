from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.core.paginacion import Page
from app.modules.repuestos.models import (
    HistorialPrecioRepuesto,
    MovimientoStock,
    Repuesto,
)
from app.modules.repuestos.schemas import RepuestoCreate, RepuestoUpdate
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork


async def crear_repuesto(
    uow: RepuestosUnitOfWork, datos: RepuestoCreate, usuario_id: int
) -> Repuesto:
    # Código duplicado entre vigentes
    stmt = select(Repuesto).where(
        Repuesto.codigo == datos.codigo, Repuesto.borrado_en.is_(None)
    )
    res = await uow.session.execute(stmt)
    if res.scalars().first() is not None:
        raise ConflictoError("Código de repuesto duplicado", "CODIGO_DUPLICADO")

    repuesto = Repuesto(
        codigo=datos.codigo,
        descripcion=datos.descripcion,
        precio=datos.precio,
        stock=datos.stock,
    )
    await uow.repuestos.add(repuesto)
    await uow.session.flush()

    if datos.stock != 0:
        movimiento = MovimientoStock(
            repuesto_id=repuesto.id,
            usuario_id=usuario_id,
            cantidad=datos.stock,
            motivo="ALTA",
            cuando=datetime.now(timezone.utc),
        )
        await uow.movimientos.add(movimiento)

    return repuesto


async def listar_repuestos(
    uow: RepuestosUnitOfWork, page: int, size: int, q: str | None = None
) -> Page[Repuesto]:
    base = select(Repuesto).where(Repuesto.borrado_en.is_(None))
    if q:
        base = base.where(Repuesto.descripcion.ilike(f"%{q}%"))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await uow.session.execute(count_stmt)).scalar_one() or 0

    stmt = base.order_by(Repuesto.id).offset((page - 1) * size).limit(size)
    res = await uow.session.execute(stmt)
    items = list(res.scalars().all())
    return Page(items=items, total=total, page=page, size=size)


async def obtener_repuesto(uow: RepuestosUnitOfWork, repuesto_id: int) -> Repuesto:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
    return repuesto


async def actualizar_repuesto(
    uow: RepuestosUnitOfWork, repuesto_id: int, datos: RepuestoUpdate, usuario_id: int
) -> Repuesto:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")

    if datos.descripcion is not None:
        repuesto.descripcion = datos.descripcion

    if datos.precio is not None and datos.precio != repuesto.precio:
        if datos.precio <= repuesto.precio:
            raise ConflictoError("Precio nuevo debe ser mayor", "PRECIO_NO_MAYOR")
        historial = HistorialPrecioRepuesto(
            repuesto_id=repuesto.id,
            usuario_id=usuario_id,
            precio_anterior=repuesto.precio,
            precio_nuevo=datos.precio,
            cuando=datetime.now(timezone.utc),
        )
        await uow.precios.add(historial)
        repuesto.precio = datos.precio

    await uow.repuestos.update(repuesto)
    return repuesto


async def baja_repuesto(uow: RepuestosUnitOfWork, repuesto_id: int) -> None:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
    await uow.repuestos.soft_delete(repuesto)


async def reponer_stock(
    uow: RepuestosUnitOfWork, repuesto_id: int, cantidad: int, usuario_id: int
) -> Repuesto:
    if cantidad <= 0:
        raise ReglaNegocioError("Cantidad inválida", "CANTIDAD_INVALIDA")
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
    repuesto.stock = repuesto.stock + cantidad
    await uow.repuestos.update(repuesto)
    movimiento = MovimientoStock(
        repuesto_id=repuesto.id,
        usuario_id=usuario_id,
        cantidad=cantidad,
        motivo="REPOSICION",
        cuando=datetime.now(timezone.utc),
    )
    await uow.movimientos.add(movimiento)
    return repuesto


async def listar_movimientos(
    uow: RepuestosUnitOfWork, repuesto_id: int
) -> list[MovimientoStock]:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
    stmt = (
        select(MovimientoStock)
        .where(MovimientoStock.repuesto_id == repuesto_id)
        .order_by(MovimientoStock.id.desc())
    )
    res = await uow.session.execute(stmt)
    return list(res.scalars().all())


async def listar_precios(
    uow: RepuestosUnitOfWork, repuesto_id: int
) -> list[HistorialPrecioRepuesto]:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
    stmt = (
        select(HistorialPrecioRepuesto)
        .where(HistorialPrecioRepuesto.repuesto_id == repuesto_id)
        .order_by(HistorialPrecioRepuesto.id.desc())
    )
    res = await uow.session.execute(stmt)
    return list(res.scalars().all())
