# Tasks

## 1. Scaffolding

- [x] 1.1 Create `app/modules/repuestos/repository.py` with `RepuestoRepository(SoftDeleteRepository)`, `MovimientoStockRepository(BaseRepository)` and `HistorialPrecioRepuestoRepository(BaseRepository)` without `update`/`delete` methods, and verify `python -c "from app.modules.repuestos.repository import *"` succeeds.
- [x] 1.2 Create `app/modules/repuestos/unit_of_work.py` with `RepuestosUnitOfWork` exposing `repuestos`, `movimientos`, `precios`, and verify import succeeds.
- [x] 1.3 Create `app/modules/repuestos/schemas.py` with `RepuestoCreate`, `RepuestoUpdate` (sin `stock`), `RepuestoRead`, `MovimientoStockRead`, `HistorialPrecioRead`, `ReponerRequest` (`extra="forbid"`), and verify import succeeds.

## 2. Service implementation (TDD)

- [x] 2.1 Write failing tests for alta con stock inicial generando movimiento ALTA and implement `crear_repuesto`; verify tests pass.
- [x] 2.2 Write failing tests for listado paginado con `q` ILIKE and implement `listar_repuestos`; verify tests pass.
- [x] 2.3 Write failing tests for consulta por id (404 si borrado) and implement `obtener_repuesto`; verify tests pass.
- [x] 2.4 Write failing tests for PATCH descripción/precio (historial, sin cambio, precio menor 409, stock no editable 422) and implement `actualizar_repuesto`; verify tests pass.
- [x] 2.5 Write failing tests for baja lógica (204, 404) and implement `baja_repuesto`; verify tests pass.
- [x] 2.6 Write failing tests for reposición (movimiento, cantidad inválida, 404) and implement `reponer_stock`; verify tests pass.
- [x] 2.7 Write failing tests for movimientos y precios (404) and implement `listar_movimientos`/`listar_precios`; verify tests pass.

## 3. Router and mounting

- [x] 3.1 Create `app/modules/repuestos/router.py` with the 8 endpoints applying RBAC and mount it in `main.py` (`router_protegido`); verify the app starts and OpenAPI lists the routes.
- [x] 3.2 Write integration tests for RBAC (solo ADMIN muta; GETs para RECEPCION/MECANICO/ADMIN) and verify pytest passes.

## 4. Verification

- [x] 4.1 Run `pytest -q` and `alembic check` (sin migraciones pendientes) and verify all pass.

## Workflow follow-up

- Archive the change after review requirements are satisfied.