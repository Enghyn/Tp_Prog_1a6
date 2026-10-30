# Spec Delta

## Purpose

Definir los modelos de datos persistentes, restricciones, índices parciales y disparadores que protegen las tablas de solo-agregado para el dominio del taller mecánico.

## ADDED Requirements

### Requirement: Modelos del dominio con restricciones
El sistema SHALL definir modelos SQLModel para `Cliente`, `Vehiculo`, `Repuesto`, `EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`, `MovimientoStock`, `HistorialPrecioRepuesto` con sus columnas, FKs, CHECKs y relaciones con `lazy="raise"`.

#### Scenario: Inserción válida de entidades
- **WHEN** se insertan entidades con valores válidos según los CHECKs definidos
- **THEN** las entidades se persisten correctamente

#### Scenario: Violación de CHECKs
- **WHEN** se intenta insertar con valores fuera de rango (anio fuera de 1950-2100, precio <= 0, stock < 0, cantidad <= 0)
- **THEN** la base de datos rechaza la operación con error de integridad

### Requirement: Índices únicos parciales para borrado lógico
El sistema SHALL crear índices únicos parciales `uq_vehiculo_patente_vigente` sobre `(patente)` WHERE `borrado_en IS NULL` y `uq_repuesto_codigo_vigente` sobre `(codigo)` WHERE `borrado_en IS NULL`.

#### Scenario: Patente reutilizable tras baja lógica
- **WHEN** un vehículo es dado de baja lógica (`borrado_en` seteado) y se intenta insertar otro vehículo con la misma patente
- **THEN** la inserción es exitosa

#### Scenario: Código de repuesto reutilizable tras baja lógica
- **WHEN** un repuesto es dado de baja lógica (`borrado_en` seteado) y se intenta insertar otro repuesto con el mismo código
- **THEN** la inserción es exitosa

### Requirement: Protección de tablas solo-agregado
El sistema SHALL proteger las tablas `historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto` mediante un trigger `BEFORE UPDATE OR DELETE` que rechace cualquier modificación o eliminación (RN-15).

#### Scenario: UPDATE sobre tabla solo-agregado rechazado
- **WHEN** se intenta ejecutar `UPDATE` sobre `movimiento_stock`, `historial_estado_orden` o `historial_precio_repuesto`
- **THEN** el trigger rechaza la operación

#### Scenario: DELETE sobre tabla solo-agregado rechazado
- **WHEN** se intenta ejecutar `DELETE` sobre `movimiento_stock`, `historial_estado_orden` o `historial_precio_repuesto`
- **THEN** el trigger rechaza la operación

### Requirement: Unicidad de ítem en orden
El sistema SHALL garantizar `UNIQUE (orden_id, repuesto_id)` en `item_orden`.

#### Scenario: Ítem duplicado en misma orden rechazado
- **WHEN** se intenta insertar dos `ItemOrden` con misma `orden_id` y `repuesto_id`
- **THEN** la base de datos rechaza la operación con `IntegrityError`
