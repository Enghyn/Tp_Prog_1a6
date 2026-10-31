from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import OrdenTrabajo


async def es_duenio_de_orden(
    sesion: AsyncSession,
    usuario_id: int,
    orden_id: int,
) -> bool:
    """
    Indica si la orden corresponde al cliente vinculado al usuario.

    Recorre `orden_trabajo -> vehiculo -> cliente` con un `EXISTS` (D6).
    `mecanico_id` no participa: RN-17 es una regla del rol CLIENTE; el acceso
    del mecánico asignado se decide por rol y estado de la orden en C-16.
    Tampoco filtra `vehiculo.borrado_en`, para conservar la propiedad del
    historial.
    """
    stmt = select(
        exists(
            select(OrdenTrabajo.id)
            .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
            .join(Cliente, Cliente.id == Vehiculo.cliente_id)
            .where(
                OrdenTrabajo.id == orden_id,
                Cliente.usuario_id == usuario_id,
            )
        )
    )
    resultado = await sesion.execute(stmt)
    return bool(resultado.scalar())
