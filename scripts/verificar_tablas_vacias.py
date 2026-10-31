"""Abortante preflight para reconstruir el esquema local sólo si está vacío."""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


TABLAS_DOMINIO = (
    "usuario",
    "asignacion_rol",
    "intento_acceso",
    "evento_seguridad",
    "cliente",
    "vehiculo",
    "estado_orden",
    "orden_trabajo",
    "item_orden",
    "historial_estado_orden",
    "repuesto",
    "movimiento_stock",
    "historial_precio_repuesto",
)


async def verificar_tablas_vacias() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL no está configurada", file=sys.stderr)
        return 2

    engine = create_async_engine(database_url, pool_pre_ping=True)
    infractoras: list[tuple[str, int]] = []
    try:
        async with engine.connect() as connection:
            for tabla in TABLAS_DOMINIO:
                resultado = await connection.execute(
                    text(f'SELECT count(*) FROM "{tabla}"')
                )
                cantidad = int(resultado.scalar_one())
                print(f"{tabla}: {cantidad} filas")
                if cantidad > 0:
                    infractoras.append((tabla, cantidad))
    except Exception as exc:
        print(f"ERROR: no se pudo verificar la base: {exc}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    if infractoras:
        print("ABORTADO: hay tablas con filas:", file=sys.stderr)
        for tabla, cantidad in infractoras:
            print(f"  - {tabla}: {cantidad}", file=sys.stderr)
        return 1

    print("OK: las 13 tablas de dominio están vacías")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verificar_tablas_vacias()))
