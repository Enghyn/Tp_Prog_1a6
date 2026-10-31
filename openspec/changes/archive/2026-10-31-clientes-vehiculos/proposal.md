# Proposal

## Why

El módulo `app/modules/clientes/` sólo contiene los modelos (`Cliente`, `Vehiculo`) y el helper `es_duenio_de_vehiculo` (C-10). No existen endpoints, repositorios, UoW, service ni schemas para gestionar clientes y vehículos, por lo que el dominio de recepción (alta de cliente, registro de vehículos, baja lógica, consulta de vehículos propios) no está expuesto. Este change habilita el flujo de recepción sobre clientes/vehículos y desbloquea C-17 (registro atómico) y C-18 (órdenes).

## What Changes

- Nuevo módulo `app/modules/clientes/`: `schemas.py`, `repository.py` (`ClienteRepository`, `VehiculoRepository(SoftDeleteRepository)`), `unit_of_work.py`, `service.py`, `router.py` (siguiendo la estructura de `app/modules/usuarios/`).
- Endpoints: `POST /clientes` (RECEPCION, ADMIN), `GET /clientes/{id}` con vehículos precargados, `POST /clientes/{id}/vehiculos`, `DELETE /vehiculos/{id}` → `204`, `GET /mis-vehiculos`.
- Borrado lógico de `Vehiculo` (RN-16): no dar de baja un vehículo con órdenes abiertas (`estado_orden.es_final = false`) → `409`.
- RN-17: `/mis-vehiculos` sólo devuelve vehículos del cliente autenticado.
- RN-01: `documento` de `Cliente` UNIQUE y patente única vigente → `409`; `404` para cliente/vehículo inexistente o dado de baja.
- Montaje del router de clientes en `router_protegido` (main.py).
- Sin migración Alembic (las tablas e índices ya existen desde C-01).

## Capabilities

### New Capabilities
- `clientes-vehiculos`: gestión de clientes y vehículos con borrado lógico, control de propiedad y guardas de órdenes abiertas.

### Modified Capabilities
- (ninguna)

## Impact

- Código afectado: `app/modules/clientes/` (nuevos archivos), `main.py` (montaje del router), tests en `tests/`.
- APIs: nuevos endpoints bajo `router_protegido`.
- Dependencias: C-10 (RBAC, `es_duenio_de_vehiculo`), C-14 (UnitOfWork).
- Sin cambios de schema/migración.