# Proposal

## Why

No existe gestión de repuestos ni de su stock: el catálogo no tiene endpoints y cualquier cambio de stock debería pasar exclusivamente por movimientos (RN-14). Sin este módulo, las órdenes de trabajo (C-18) no podrán consumir ni reponer repuestos, y el historial de precios (RN-20) no tendrá punto de escritura. Es el prerequisito para el consumo de stock en órdenes.

## What Changes

- Nuevo módulo `app/modules/repuestos/` con `RepuestoRepository(SoftDeleteRepository)`, `MovimientoStockRepository`, `HistorialPrecioRepuestoRepository`, `RepuestosUnitOfWork`, servicio y router.
- 8 endpoints: `GET /repuestos` (paginado, `q` ILIKE), `GET /repuestos/{id}`, `POST /repuestos` (ADMIN, stock inicial + movimiento ALTA en mismo UoW), `PATCH /repuestos/{id}` (descripción y/o precio), `DELETE /repuestos/{id}` (204 lógico), `POST /repuestos/{id}/reponer`, `GET /repuestos/{id}/movimientos`, `GET /repuestos/{id}/precios`.
- RN-14: `stock` no editable por PATCH; rechazo con 422/400.
- RN-20: PATCH con precio distinto genera línea en `historial_precio_repuesto` en la misma transacción; sin cambio no genera línea; `precio_nuevo <= precio_anterior` → 409.
- Montaje del router en `router_protegido` en `main.py`.
- Sin migración Alembic: el esquema ya define las tablas, índices y triggers.

## Capabilities

### New Capabilities

- `repuestos-stock`: Catálogo de repuestos con stock gobernado exclusivamente por movimientos, reposición, movimientos de stock e historial de precios.

### Modified Capabilities

(none)

## Impact

- Código: `app/modules/repuestos/*`, `main.py` (montaje del router).
- APIs: 8 nuevos endpoints bajo `/repuestos`.
- Dependencias: C-10 (RBAC) y C-14 (Unit of Work) ya archivadas.
- Sin cambios de esquema ni migraciones.