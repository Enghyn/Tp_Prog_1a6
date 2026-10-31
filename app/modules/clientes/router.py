from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import obtener_usuario_actual, require_roles
from app.modules.clientes.schemas import ClienteCreate, ClienteRead, VehiculoCreate, VehiculoRead
from app.modules.clientes.service import (
    crear_cliente,
    obtener_cliente_con_vehiculos,
    crear_vehiculo,
    baja_vehiculo,
    mis_vehiculos,
)
from app.modules.clientes.unit_of_work import ClientesUnitOfWork

async def get_uow_clientes(session: AsyncSession = Depends(get_session)):
    return ClientesUnitOfWork(session)


router = APIRouter()
router_publico = APIRouter()
router_autenticado = APIRouter()


@router_autenticado.post("/clientes", response_model=ClienteRead, status_code=201, dependencies=[Depends(require_roles("RECEPCION", "ADMIN"))])
async def post_cliente(datos: ClienteCreate, uow: ClientesUnitOfWork = Depends(get_uow_clientes)):
    cliente = await crear_cliente(uow, datos)
    await uow.commit()
    return cliente


@router_autenticado.get("/clientes/{cliente_id}", response_model=ClienteRead)
async def get_cliente(cliente_id: int, uow: ClientesUnitOfWork = Depends(get_uow_clientes)):
    cliente = await obtener_cliente_con_vehiculos(uow, cliente_id)
    return cliente


@router_autenticado.post("/clientes/{cliente_id}/vehiculos", response_model=VehiculoRead, status_code=201, dependencies=[Depends(require_roles("RECEPCION", "ADMIN"))])
async def post_vehiculo(cliente_id: int, datos: VehiculoCreate, uow: ClientesUnitOfWork = Depends(get_uow_clientes)):
    vehiculo = await crear_vehiculo(uow, cliente_id, datos)
    await uow.commit()
    return vehiculo


@router_autenticado.delete("/vehiculos/{vehiculo_id}", status_code=204, dependencies=[Depends(require_roles("RECEPCION", "ADMIN"))])
async def delete_vehiculo(vehiculo_id: int, uow: ClientesUnitOfWork = Depends(get_uow_clientes)):
    await baja_vehiculo(uow, vehiculo_id)
    await uow.commit()
    return Response(status_code=204)


@router_autenticado.get("/mis-vehiculos", response_model=list[VehiculoRead], dependencies=[Depends(require_roles("CLIENTE"))])
async def get_mis_vehiculos(uow: ClientesUnitOfWork = Depends(get_uow_clientes), sesion_actual=Depends(obtener_usuario_actual)):
    vehiculos = await mis_vehiculos(uow, sesion_actual.usuario.id)
    return vehiculos