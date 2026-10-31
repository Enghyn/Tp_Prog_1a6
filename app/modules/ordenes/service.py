from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictoError, NoEncontradoError, ProhibidoError, ReglaNegocioError
from app.core.paginacion import Page
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
from app.modules.ordenes.repository import es_duenio_de_orden
from app.modules.ordenes.schemas import OrdenCreate
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.repuestos.models import Repuesto
from app.modules.usuarios.repository import obtener_roles_vigentes_por_usuario


async def crear_orden(
    uow: OrdenesUnitOfWork, datos: OrdenCreate, usuario_id: int
) -> OrdenTrabajo:
    # RN-19: catálogo no vacío
    total_estados = await uow.estados.count() if hasattr(uow.estados, "count") else None
    if total_estados is None:
        # fallback
        estados = await uow.estados.get_all()
        total_estados = len(estados)
    if total_estados == 0:
        raise ConflictoError("Catálogo de estados vacío", "CATALOGO_ESTADOS_VACIO")

    # estado inicial
    estado_pendiente = await uow.session.get(EstadoOrden, "PENDIENTE")
    if estado_pendiente is None:
        raise ConflictoError("Estado inicial no disponible", "ESTADO_INICIAL_NO_DISPONIBLE")

    # vehículo existe (incluyendo dados de baja, para conservar propiedad)
    vehiculo = await uow.session.get(Vehiculo, datos.vehiculo_id)
    if vehiculo is None:
        raise NoEncontradoError("Vehículo no encontrado", "VEHICULO_NO_ENCONTRADO")

    # dedup ítems (RN-10)
    vistos: set[int] = set()
    for item in datos.items:
        if item.repuesto_id in vistos:
            raise ReglaNegocioError("Ítem repetido", "ITEM_REPETIDO")
        vistos.add(item.repuesto_id)

    # validar repuestos vigentes (RN-16) y copiar precio
    lineas: list[tuple[int, int, Decimal]] = []
    for item in datos.items:
        repuesto = await uow.session.get(Repuesto, item.repuesto_id)
        if repuesto is None:
            raise NoEncontradoError("Repuesto no encontrado", "REPUESTO_NO_ENCONTRADO")
        if repuesto.borrado_en is not None:
            raise ConflictoError("Repuesto dado de baja", "REPUESTO_DADO_DE_BAJA")
        lineas.append((item.repuesto_id, item.cantidad, repuesto.precio))

    total = sum((Decimal(cantidad) * precio for _, cantidad, precio in lineas), Decimal("0"))

    ahora = datetime.now(timezone.utc)
    orden = OrdenTrabajo(
        vehiculo_id=datos.vehiculo_id,
        mecanico_id=None,
        estado="PENDIENTE",
        falla=datos.falla,
        creada_en=ahora,
        total=total,
    )
    await uow.ordenes.add(orden)
    await uow.session.flush()

    for repuesto_id, cantidad, precio in lineas:
        item = ItemOrden(
            orden_id=orden.id,
            repuesto_id=repuesto_id,
            cantidad=cantidad,
            precio_unitario=precio,
        )
        await uow.items.add(item)

    historial = HistorialEstadoOrden(
        orden_id=orden.id,
        desde_estado=None,
        hasta_estado="PENDIENTE",
        usuario_id=usuario_id,
        cuando=ahora,
    )
    await uow.historial.add(historial)

    # precarga
    return await uow.ordenes.get_by_id(orden.id)


async def obtener_orden(
    uow: OrdenesUnitOfWork, orden_id: int, usuario_id: int
) -> OrdenTrabajo:
    orden = await uow.ordenes.get_by_id(orden_id)
    if orden is None:
        raise NoEncontradoError("Orden no encontrada", "ORDEN_NO_ENCONTRADA")

    roles = await obtener_roles_vigentes_por_usuario(uow.session, usuario_id)

    permitido = False
    if "RECEPCION" in roles or "ADMIN" in roles:
        permitido = True
    elif orden.mecanico_id == usuario_id:
        permitido = True
    elif await es_duenio_de_orden(uow.session, usuario_id, orden_id):
        permitido = True

    if not permitido:
        raise ProhibidoError("Sin permiso", "SIN_PERMISO")

    return orden


async def listar_ordenes(
    uow: OrdenesUnitOfWork, page: int, size: int, estado: str | None = None
) -> Page[OrdenTrabajo]:
    if estado is not None:
        est = await uow.session.get(EstadoOrden, estado)
        if est is None:
            raise ReglaNegocioError("Estado inválido", "ESTADO_INVALIDO")

    total = await uow.ordenes.count(estado=estado)
    offset = (page - 1) * size
    items = await uow.ordenes.get_all(limit=size, offset=offset, estado=estado)
    return Page(items=list(items), total=total, page=page, size=size)


async def mis_ordenes(
    uow: OrdenesUnitOfWork, usuario_id: int, page: int, size: int
) -> Page[OrdenTrabajo]:
    stmt = select(Cliente).where(Cliente.usuario_id == usuario_id)
    res = await uow.session.execute(stmt)
    cliente = res.scalars().first()
    if cliente is None:
        raise NoEncontradoError("Cliente no vinculado", "CLIENTE_NO_VINCULADO")

    # count
    count_stmt = (
        select(func.count())
        .select_from(OrdenTrabajo)
        .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
        .where(Vehiculo.cliente_id == cliente.id)
    )
    total = (await uow.session.execute(count_stmt)).scalar_one() or 0

    offset = (page - 1) * size
    stmt2 = (
        select(OrdenTrabajo)
        .options(
            selectinload(OrdenTrabajo.vehiculo),
            selectinload(OrdenTrabajo.items).selectinload(ItemOrden.repuesto),
            selectinload(OrdenTrabajo.mecanico),
        )
        .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
        .where(Vehiculo.cliente_id == cliente.id)
        .order_by(OrdenTrabajo.id)
        .offset(offset)
        .limit(size)
    )
    res2 = await uow.session.execute(stmt2)
    items = list(res2.scalars().all())
    return Page(items=items, total=total, page=page, size=size)


async def listar_estados(uow: OrdenesUnitOfWork) -> list[EstadoOrden]:
    return list(await uow.estados.get_all())