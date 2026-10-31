# Design

## Context

El módulo `app/modules/repuestos/` ya define los modelos `Repuesto`, `MovimientoStock` e `HistorialPrecioRepuesto` (con sus CHECKs e índice parcial). No hay repositorios, servicio ni router. El esquema de base de datos y los triggers RN-11 ya están en la migración inicial. Ver `proposal.md` para motivación. Se sigue el patrón del módulo `clientes` (C-15).

## Goals / Non-Goals

**Goals:**
- Endpoints de catálogo y stock gobernados exclusivamente por movimientos.
- Repositorios append-only para `MovimientoStock` e `HistorialPrecioRepuesto` (sin `update`/`delete`) para honrar RN-11/triggers.
- `RepuestoRepository` extendiendo `SoftDeleteRepository` (baja lógica).
- Una única transacción por operación mutante (UoW).

**Non-Goals:**
- Consumo de stock por órdenes (C-18).
- Concurrencia avanzada / bloqueos (cap. 7 fuera de alcance).
- Migraciones Alembic nuevas.

## Decisions

1. **Estructura de módulo**: espejo de `clientes`: `models.py` (existente), `repository.py`, `unit_of_work.py`, `schemas.py`, `service.py`, `router.py`. UoW expone `repuestos`, `movimientos`, `precios`.
2. **RepuestoRepository extends SoftDeleteRepository** para reutilizar baja lógica y `get_by_id` filtrando vigentes. `MovimientoStockRepository` y `HistorialPrecioRepuestoRepository` extienden `BaseRepository` pero NO exponen `update`/`delete` (append-only, RN-11).
3. **Stock inicial en alta**: en el mismo UoW se crea el `Repuesto` y un `MovimientoStock` con cantidad = stock inicial. No se persiste `tipo` (el modelo usa `motivo`); se usa `motivo="ALTA"` para el movimiento inicial. Reposición usa `motivo="REPOSICION"`.
4. **PATCH de precio**: comparar en servicio; si difiere, insertar `HistorialPrecioRepuesto(precio_anterior, precio_nuevo)` en el mismo UoW. Si `precio_nuevo <= precio_anterior` → `ConflictoError` (409). Si no cambia, no se genera línea. `stock` no es campo del schema `RepuestoUpdate` (`extra="forbid"`), por lo que enviarlo produce 422 automáticamente (RN-14).
5. **Paginación y búsqueda**: `GET /repuestos` usa `page`/`size` y `q` opcional; consulta con `ILIKE` sobre `descripcion` y `count` total. Respuesta `Page[RepuestoRead]`.
6. **RBAC**: GET de listado y detalle disponibles para `RECEPCION`, `MECANICO`, `ADMIN` (lectura operativa). Mutaciones (POST/PATCH/DELETE/reponer/movimientos/precios) solo `ADMIN`. No se expone a `CLIENTE` (los clientes no consultan repuestos).
7. **Manejo de stock nunca negativo**: validación en servicio antes de reponer/consumir; el CHECK de BD es red de seguridad. Reposición exige cantidad > 0.
8. **No migración**: el esquema ya existe; solo se agrega código.

## Risks / Trade-offs

- [Race en stock concurrente] → fuera de alcance (cap. 7); el CHECK de BD evita stock negativo a nivel fila.
- [Append-only triggers] → los repositorios no exponen update/delete; cualquier intento directo falla en BD.
- [Índice parcial de código] → reutilización de código tras baja lógica funciona por el filtro `borrado_en IS NULL`.

## Migration Plan

No hay migración. Desplegar código y montar el router en `router_protegido`. Rollback: revertir el commit de código.

## Open Questions

- Ninguna bloqueante. Los nombres de códigos de error siguen el patrón del módulo clientes.