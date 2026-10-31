from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clientes.models import Cliente, Vehiculo


async def es_duenio_de_vehiculo(
    sesion: AsyncSession,
    usuario_id: int,
    vehiculo_id: int,
) -> bool:
    """
    Indica si el vehículo pertenece a la ficha de cliente vinculada al usuario.

    Usa un `EXISTS` con join `vehiculo -> cliente` (D6): no materializa
    entidades ni navega relaciones `lazy="raise"`. No filtra `borrado_en`
    porque la propiedad es histórica: un vehículo dado de baja sigue
    perteneciendo a su cliente para consultar el historial.
    """
    stmt = select(
        exists(
            select(Vehiculo.id)
            .join(Cliente, Cliente.id == Vehiculo.cliente_id)
            .where(
                Vehiculo.id == vehiculo_id,
                Cliente.usuario_id == usuario_id,
            )
        )
    )
    resultado = await sesion.execute(stmt)
    return bool(resultado.scalar())
