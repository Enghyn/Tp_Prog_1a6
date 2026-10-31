# Proposal

## Why

El módulo `app/modules/ordenes/` solo define los modelos (`EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`); no existen repositorios, servicio ni endpoints. Sin ellos no se puede abrir ni consultar órdenes de trabajo, que es el objeto central del taller. La apertura debe ser atómica: los precios se copian del catálogo de repuestos, el total se calcula en el servidor y se deja una línea inicial de historial en la misma transacción. La consulta debe respetar RN-17 (cliente ve solo las propias) y RN-19 (catálogo de estados vacío es un error de apertura).

## What Changes

- Nuevo módulo `app/modules/ordenes/` con `OrdenRepository`, `ItemOrdenRepository`, `EstadoOrdenRepository` (solo lectura), `HistorialEstadoOrdenRepository`, `OrdenesUnitOfWork`, servicio y router, espejo de `clientes`/`repuestos`.
- 6 endpoints: `POST /ordenes` (RECEPCION/ADMIN), `GET /ordenes` (RECEPCION/ADMIN/MECANICO), `GET /ordenes/{id}` (personal o dueño), `GET /mis-ordenes` (CLIENTE), `GET /estados-orden` (autenticado).
- Schemas de entrada sin `precio_unitario` ni `total` (`extra="forbid"`); ítems sin repetir y `cantidad > 0` → 422 (RN-10).
- `POST /ordenes`: valida repuestos vigentes (RN-16), copia `precio_unitario` actual, calcula `total` en servidor, crea orden `PENDIENTE` + línea de historial `desde_estado=NULL → PENDIENTE` en el mismo UoW; catálogo vacío → 409 (RN-19).
- Precarga con `selectinload` de `vehiculo`, `items.repuesto` y `mecanico` (sin N+1).
- Montaje del router en `router_protegido` en `main.py`.
- Sin migración Alembic: el esquema ya define las tablas, índices, CHECKs, triggers y seed.

## Capabilities

### New Capabilities

- `ordenes-trabajo`: Apertura y consulta de órdenes de trabajo con precios y totales calculados en servidor, autorización por propiedad (RN-17) y catálogo de estados (RN-19).

### Modified Capabilities

(none)

## Impact

- Código: `app/modules/ordenes/*` (repository, unit_of_work, schemas, service, router), `main.py` (montaje).
- APIs: 6 nuevos endpoints bajo `/ordenes` y `/estados-orden`.
- Dependencias: C-15 (clientes-vehiculos) y C-16 (repuestos-stock) archivadas; C-04 (notificaciones) no requerida en esta fase.
- Sin cambios de esquema ni migraciones.
- Requiere relación `ItemOrden.repuesto` en el modelo (solo ORM, sin migración) para la precarga `items.repuesto`.
