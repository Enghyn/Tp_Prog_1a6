# Tasks

## 1. Modelos de Clientes y Vehículos

- [x] 1.1 Definir modelos `Cliente` y `Vehiculo` en `app/modules/clientes/models.py` con relaciones `lazy="raise"`, CHECK `anio >= 1950 AND anio <= 2100`, índice único parcial `uq_vehiculo_patente_vigente (patente) WHERE borrado_en IS NULL`, y verificar mediante tests unitarios de instanciación e inspección de metadatos.
- [x] 1.2 Implementar tests en `test/test_domain_models.py` verificando que la inserción de vehículo con año inválido falla y que una patente dada de baja lógica permite reutilización.

## 2. Modelos de Repuestos, Stock y Precios

- [x] 2.1 Definir modelos `Repuesto`, `MovimientoStock` y `HistorialPrecioRepuesto` en `app/modules/repuestos/models.py` con `lazy="raise"`, CHECKs (`precio > 0`, `stock >= 0`, `cantidad != 0`, `precio_nuevo > precio_anterior`), índice parcial `uq_repuesto_codigo_vigente (codigo) WHERE borrado_en IS NULL`, y verificar mediante tests unitarios de modelos.
- [x] 2.2 Implementar tests en `test/test_domain_models.py` validando restricciones de precio positivo, stock no negativo, cantidad no nula, incremento de precio e índice parcial de código de repuesto tras baja lógica en PostgreSQL.

## 3. Modelos de Órdenes de Trabajo e Historial

- [x] 3.1 Definir modelos `EstadoOrden`, `OrdenTrabajo`, `ItemOrden` y `HistorialEstadoOrden` en `app/modules/ordenes/models.py` con catálogo `EstadoOrden` (PK string, `posicion` UNIQUE, `es_final`), CHECK `total >= 0`, CHECK `cantidad > 0`, `precio_unitario > 0`, restricción `UNIQUE (orden_id, repuesto_id)`, `cascade="all, delete-orphan"` en `items`, `lazy="raise"` en todas las relaciones, y verificar mediante tests unitarios de modelos.
- [x] 3.2 Implementar tests en `test/test_domain_models.py` verificando unicidad de `(orden_id, repuesto_id)`, validación de totales y cascadas de eliminación huérfana de ítems en PostgreSQL.

## 4. Migración 002: Dominio del Taller

- [x] 4.1 Registrar importaciones de los nuevos modelos en `migrations/env.py` y crear la migración `002_dominio_taller.py` conteniendo todas las tablas, FKs, CHECKs e índices parciales del dominio.
- [x] 4.2 Probar la migración en base de datos PostgreSQL real ejecutando `alembic upgrade head` y verificar rollback limpio con `alembic downgrade -1` y re-aplicación a head.

## 5. Migración 003: Tablas de Sólo Agregado (Triggers RN-15)

- [x] 5.1 Crear la migración `003_solo_agregado.py` escrita a mano con función PL/pgSQL y triggers `BEFORE UPDATE OR DELETE` sobre `movimiento_stock`, `historial_estado_orden` y `historial_precio_repuesto` (RN-15).
- [x] 5.2 Crear el script `test/solo_agregado.sql` con casos de prueba SQL directos que demuestren el bloqueo de UPDATE y DELETE en las tres tablas.
- [x] 5.3 Implementar tests en `test/test_solo_agregado.py` verificando mediante pytest y asyncpg que cualquier operación de UPDATE o DELETE sobre las tablas de sólo agregado lanza excepción de base de datos.

## 6. Verificación Integral y Suite de Tests

- [x] 6.1 Ejecutar la suite completa de pruebas de modelos de dominio y solo agregado en PostgreSQL (`pytest test/test_domain_models.py test/test_solo_agregado.py`) verificando que todas las aserciones pasan y no hay regresiones.
