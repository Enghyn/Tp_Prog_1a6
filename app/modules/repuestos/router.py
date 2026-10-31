from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import SesionActual, obtener_usuario_actual, require_roles
from app.core.paginacion import Page, PageParams
from app.modules.repuestos.schemas import (
    HistorialPrecioRead,
    MovimientoStockRead,
    ReponerRequest,
    RepuestoCreate,
    RepuestoRead,
    RepuestoUpdate,
)
from app.modules.repuestos.service import (
    actualizar_repuesto,
    baja_repuesto,
    crear_repuesto,
    listar_movimientos,
    listar_precios,
    listar_repuestos,
    obtener_repuesto,
    reponer_stock,
)
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork

async def get_uow_repuestos(session: AsyncSession = Depends(get_session)):
    return RepuestosUnitOfWork(session)


router_autenticado = APIRouter()


@router_autenticado.get("/repuestos", response_model=Page[RepuestoRead], dependencies=[Depends(require_roles("RECEPCION", "MECANICO", "ADMIN"))])
async def get_repuestos(
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    q: str | None = None,
):
    return await listar_repuestos(uow, page=page, size=size, q=q)


@router_autenticado.get("/repuestos/{repuesto_id}", response_model=RepuestoRead, dependencies=[Depends(require_roles("RECEPCION", "MECANICO", "ADMIN"))])
async def get_repuesto(
    repuesto_id: int,
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    return await obtener_repuesto(uow, repuesto_id)


@router_autenticado.post(
    "/repuestos", response_model=RepuestoRead, status_code=201,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def post_repuesto(
    datos: RepuestoCreate,
    sesion_actual: SesionActual = Depends(require_roles("ADMIN")),
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    repuesto = await crear_repuesto(uow, datos, sesion_actual.usuario.id)
    await uow.commit()
    return repuesto


@router_autenticado.patch(
    "/repuestos/{repuesto_id}", response_model=RepuestoRead,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def patch_repuesto(
    repuesto_id: int,
    datos: RepuestoUpdate,
    sesion_actual: SesionActual = Depends(require_roles("ADMIN")),
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    repuesto = await actualizar_repuesto(uow, repuesto_id, datos, sesion_actual.usuario.id)
    await uow.commit()
    return repuesto


@router_autenticado.delete(
    "/repuestos/{repuesto_id}", status_code=204,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def delete_repuesto(
    repuesto_id: int,
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    await baja_repuesto(uow, repuesto_id)
    await uow.commit()
    return Response(status_code=204)


@router_autenticado.post(
    "/repuestos/{repuesto_id}/reponer", response_model=RepuestoRead,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def post_reponer(
    repuesto_id: int,
    datos: ReponerRequest,
    sesion_actual: SesionActual = Depends(require_roles("ADMIN")),
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    repuesto = await reponer_stock(uow, repuesto_id, datos.cantidad, sesion_actual.usuario.id)
    await uow.commit()
    return repuesto


@router_autenticado.get(
    "/repuestos/{repuesto_id}/movimientos",
    response_model=list[MovimientoStockRead],
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_movimientos(
    repuesto_id: int,
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    return await listar_movimientos(uow, repuesto_id)


@router_autenticado.get(
    "/repuestos/{repuesto_id}/precios",
    response_model=list[HistorialPrecioRead],
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_precios(
    repuesto_id: int,
    uow: RepuestosUnitOfWork = Depends(get_uow_repuestos),
):
    return await listar_precios(uow, repuesto_id)


router = router_autenticado
router_publico = APIRouter()
