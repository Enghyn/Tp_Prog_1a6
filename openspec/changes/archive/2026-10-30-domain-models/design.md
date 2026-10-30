# Design

## Context

Este change extiende el modelo de datos con el dominio del taller. Ya existen los modelos de auth (C-06) y la infraestructura de base de datos (C-05). Se deben seguir las reglas duras: `lazy="raise"`, `selectinload` explícito, Alembic async sin `create_all`, tests contra PostgreSQL real, FKs y constraints correctas.

## Goals / Non-Goals

**Goals:**
- Definir todos los modelos del dominio con relaciones, cascadas y constraints
- Crear migración `002_dominio_taller` con FKs, CHECKs, índices parciales
- Crear migración `003_solo_agregado` con trigger que bloquee UPDATE/DELETE en tablas de solo-agregado
- Validar con tests contra PostgreSQL real

**Non-Goals:**
- Repositorios/servicios/UoW (C-13/C-14)
- Endpoints (C-15/C-16/C-18)
- Lógica de negocio compleja (se implementa en servicios)

## Decisions

- **Ubicación de modelos**: Distribución por módulo funcional según arquitectura obligatoria (KB §02):
  - `app/modules/clientes/models.py`: `Cliente`, `Vehiculo`
  - `app/modules/repuestos/models.py`: `Repuesto`, `MovimientoStock`, `HistorialPrecioRepuesto`
  - `app/modules/ordenes/models.py`: `EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`
- **Relaciones**: `lazy="raise"` en todas, `cascade="all, delete-orphan"` en composiciones (`ItemOrden` desde `OrdenTrabajo`), y `foreign_keys` explícitas para desambiguar múltiples FKs (ej. `desde_estado` / `hasta_estado` en `HistorialEstadoOrden`).
- **Borrado lógico**: `Vehiculo.borrado_en` y `Repuesto.borrado_en` con índices únicos parciales en PostgreSQL (`WHERE borrado_en IS NULL`).
- **Tablas solo-agregado**: protegidas por trigger en migración manual `003_solo_agregado` (función PL/pgSQL `bloquear_modificacion_solo_agregado()` + trigger `BEFORE UPDATE OR DELETE` en `movimiento_stock`, `historial_estado_orden`, `historial_precio_repuesto`). Script complementario de verificación en `test/solo_agregado.sql`.
- **EstadoOrden**: catálogo con PK `codigo` (string) y `posicion` UNIQUE (integer). Filas fijas preparadas para seed en C-08.

## Migration Plan

1. Agregar modelos en módulos correspondientes, importar en `migrations/env.py`
2. Generar `002_dominio_taller` con autogenerate, revisar y ajustar índices parciales y CHECKs
3. Crear manualmente `003_solo_agregado.py` con función y triggers
4. Aplicar y probar

## Risks / Trade-offs

- **Trigger complejo**: debe lanzarse como excepción para bloquear correctamente
- **Índices parciales**: autogenerate puede no detectarlos correctamente, requiere revisión manual
- **Relaciones bidireccionales**: mantener `lazy="raise"` y especificar `foreign_keys` cuando hay ambigüedad
