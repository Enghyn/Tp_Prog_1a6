from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import SesionActual, obtener_usuario_actual, require_roles
from app.core.paginacion import Page, PageParams
from app.modules.ordenes.schemas import (
    EstadoOrdenRead,
    OrdenCreate,
    OrdenRead,
)
from app.modules.ordenes.service import (
    crear_orden,
    listar_estados,
    listar_ordenes,
    mis_ordenes,
    obtener_orden,
)
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork


async def get_uow_ordenes(session: AsyncSession = Depends(get_session)):
    return OrdenesUnitOfWork(session)


router = APIRouter()
router_publico = APIRouter()
router_autenticado = APIRouter()


@router_autenticado.post(
    "/ordenes", response_model=OrdenRead, status_code=201,
    dependencies=[Depends(require_roles("RECEPCION", "ADMIN"))],
)
async def post_orden(
    datos: OrdenCreate,
    sesion_actual: SesionActual = Depends(require_roles("RECEPCION", "ADMIN")),
    uow: OrdenesUnitOfWork = Depends(get_uow_ordenes),
):
    orden = await crear_orden(uow, datos, sesion_actual.usuario.id)
    await uow.commit()
    return orden


@router_autenticado.get(
    "/ordenes", response_model=Page[OrdenRead],
    dependencies=[Depends(require_roles("RECEPCION", "MECANICO", "ADMIN"))],
)
async def get_ordenes(
    uow: OrdenesUnitOfWork = Depends(get_uow_ordenes),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    estado: str | None = None,
):
    return await listar_ordenes(uow, page=page, size=size, estado=estado)


@router_autenticado.get("/ordenes/{orden_id}", response_model=OrdenRead)
async def get_orden(
    orden_id: int,
    sesion_actual: SesionActual = Depends(obtener_usuario_actual),
    uow: OrdenesUnitOfWork = Depends(get_uow_ordenes),
):
    orden = await obtener_orden(uow, orden_id, sesion_actual.usuario.id)
    return orden


@router_autenticado.get(
    "/mis-ordenes", response_model=Page[OrdenRead],
    dependencies=[Depends(require_roles("CLIENTE"))],
)
async def get_mis_ordenes(
    uow: OrdenesUnitOfWork = Depends(get_uow_ordenes),
    sesion_actual: SesionActual = Depends(obtener_usuario_actual),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
):
    return await mis_ordenes(uow, sesion_actual.usuario.id, page=page, size=size)


@router_autenticado.get(
    "/estados-orden", response_model=list[EstadoOrdenRead],
)
async def get_estados_orden(
    uow: OrdenesUnitOfWork = Depends(get_uow_ordenes),
    sesion_actual: SesionActual = Depends(obtener_usuario_actual),
):
    return await listar_estados(uow)