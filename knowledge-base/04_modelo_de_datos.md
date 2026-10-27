# 04 - Modelo de Datos y Esquema Relacional

El esquema de base de datos se gestiona exclusivamente mediante Alembic (con plantilla asincrónica). Consta de 13 tablas con restricciones estrictas, claves foráneas, índices y disparadores.

## Tablas y Restricciones Principales

1. **`usuario`**:
   - Columnas: `id`, `email` (UNIQUE), `nombre`, `password_hash`, `activo` (bool), `debe_cambiar_password` (bool), `password_cambiada_en` (timestamptz, nulo permitido).
2. **`asignacion_rol`**:
   - Columnas: `id`, `usuario_id`, `rol` (CHECK: ADMIN, RECEPCION, MECANICO, CLIENTE), `desde`, `vence_en` (nulo), `revocada_en` (nulo), `otorgada_por` (nulo).
   - Restricción: Índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL`.
3. **`intento_acceso`**:
   - Columnas: `id`, `cuando`, `email`, `ip`, `exito` (bool).
   - Restricción: Índice `(email, ip, cuando)`.
4. **`evento_seguridad`**:
   - Columnas: `id`, `cuando`, `actor` (texto), `accion`.
5. **`cliente`**:
   - Columnas: `id`, `usuario_id` (UNIQUE, nulo permitido), `nombre`, `documento` (UNIQUE), `telefono`.
6. **`vehiculo`**:
   - Columnas: `id`, `cliente_id`, `patente`, `marca`, `modelo`, `anio` (CHECK: 1950 a 2100), `borrado_en` (timestamptz, nulo).
   - Restricción: Índice único parcial `(patente) WHERE borrado_en IS NULL`.
7. **`repuesto`**:
   - Columnas: `id`, `codigo`, `descripcion`, `precio` (NUMERIC 10,2, CHECK > 0), `stock` (CHECK >= 0), `borrado_en` (timestamptz, nulo).
   - Restricción: Índice único parcial `(codigo) WHERE borrado_en IS NULL`.
8. **`estado_orden`** (Catálogo de referencia):
   - Columnas: `codigo` (PK), `descripcion`, `posicion` (UNIQUE), `es_final` (bool).
   - Filas cargadas por `seed.py`: PENDIENTE (pos 1), EN_REPARACION (pos 2), TERMINADA (pos 3, es_final=true), CANCELADA (pos 4, es_final=true).
9. **`orden_trabajo`**:
   - Columnas: `id`, `vehiculo_id`, `mecanico_id` (nulo), `estado` (FK a `estado_orden.codigo`), `falla`, `creada_en`, `total` (NUMERIC 12,2, CHECK >= 0).
10. **`item_orden`** (Composición):
    - Columnas: `id`, `orden_id`, `repuesto_id`, `cantidad` (CHECK > 0), `precio_unitario` (NUMERIC 10,2, CHECK > 0).
    - Restricción: `UNIQUE (orden_id, repuesto_id)`.
11. **`historial_estado_orden`** (Sólo agregado):
    - Columnas: `id`, `orden_id`, `desde_estado` (nulo, FK), `hasta_estado` (FK), `usuario_id`, `cuando`.
12. **`movimiento_stock`** (Sólo agregado):
    - Columnas: `id`, `repuesto_id`, `orden_id` (nulo), `usuario_id`, `cantidad` (CHECK != 0), `motivo`, `cuando`.
13. **`historial_precio_repuesto`** (Sólo agregado):
    - Columnas: `id`, `repuesto_id`, `usuario_id`, `precio_anterior` (NUMERIC 10,2), `precio_nuevo` (NUMERIC 10,2, CHECK > 0 AND > precio_anterior), `cuando`.

## Características Clave
- **Borrado Lógico con Índices Parciales**: Permite revender un vehículo con la misma patente o dar de alta repuestos con códigos previamente dados de baja (`WHERE borrado_en IS NULL`).
- **Tablas de Sólo Agregado (RN-15)**: Protegidas mediante un trigger en PostgreSQL que rechaza cualquier operación `UPDATE` o `DELETE`.
