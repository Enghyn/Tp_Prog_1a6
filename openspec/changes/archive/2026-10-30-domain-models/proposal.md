# Proposal

## Why

El sistema necesita modelar el dominio del taller (clientes, vehículos, repuestos, órdenes de trabajo e historial) para soportar la gestión operativa. Sin estos modelos no se pueden implementar las funcionalidades de clientes/vehículos, repuestos/stock, órdenes y sus reglas de negocio. Este change introduce todos los modelos del dominio junto con sus migraciones y los triggers que protegen las tablas de solo-agregado.

## What Changes

- **Modelos de dominio**: `Cliente`, `Vehiculo`, `Repuesto`, `EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`, `MovimientoStock`, `HistorialPrecioRepuesto` en `app/modules/domain/models.py` (o distribuidos por módulos) con SQLModel `table=True`, `lazy="raise"`, relaciones bidireccionales y `cascade="all, delete-orphan"` donde corresponda.
- **Restricciones**: CHECKs para `anio` (1950-2100), `precio > 0`, `stock >= 0`, `cantidad > 0`, `cantidad != 0`, `precio_nuevo > precio_anterior`; `UNIQUE (orden_id, repuesto_id)` en `ItemOrden`; FKs correctas.
- **Índices parciales**: `uq_vehiculo_patente_vigente` sobre `(patente)` con `WHERE borrado_en IS NULL`; `uq_repuesto_codigo_vigente` sobre `(codigo)` con `WHERE borrado_en IS NULL`.
- **Migración `002_dominio_taller`**: crea todas las tablas, FKs, CHECKs e índices parciales.
- **Migración `003_solo_agregado`**: función + trigger `BEFORE UPDATE OR DELETE` en `movimiento_stock`, `historial_estado_orden`, `historial_precio_repuesto` para bloquear modificaciones/eliminaciones (RN-15). Escribir a mano.
- **Tests**: validación de restricciones, índices parciales (patente reutilizable tras baja lógica), protección de tablas solo-agregado, ítem duplicado en orden rechazado.
