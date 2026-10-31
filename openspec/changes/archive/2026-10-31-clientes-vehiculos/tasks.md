# Tasks

## 1. Safety-net baseline
- [x] 1.1 Ejecutar suite completa actual (`pytest -q`) y registrar verde como baseline.

## 2. Schemas y repositorios (TDD)
- [x] 2.1 RED: test alta cliente + consulta con vehículos.
- [x] 2.2 GREEN: implementar `schemas.py` (ClienteCreate/Read, VehiculoCreate/Read) con `extra="forbid"`.
- [x] 2.3 GREEN: implementar `ClienteRepository` y `VehiculoRepository(SoftDeleteRepository)` en `repository.py`.
- [x] 2.4 GREEN: implementar `unit_of_work.py` (`ClientesUnitOfWork`).

## 3. Endpoints (TDD)
- [x] 3.1 RED: test patente duplicada vigente → 409; patente reusable tras baja lógica.
- [x] 3.2 GREEN: `service.py` + `router.py` POST /clientes, GET /clientes/{id}, POST /clientes/{id}/vehiculos.
- [x] 3.3 RED: test baja con orden abierta → 409; baja exitosa → 204.
- [x] 3.4 GREEN: DELETE /vehiculos/{id} con guard RN-16.
- [x] 3.5 RED: test /mis-vehiculos solo vehículos del cliente; 403 sin rol.
- [x] 3.6 GREEN: GET /mis-vehiculos resolviendo cliente por usuario_id.
- [x] 3.7 Montar router en `main.py` (`router_protegido`).

## 4. Refactor-verification
- [x] 4.1 Ejecutar suite completa; contratos HTTP sin cambios.
- [x] 4.2 `alembic check` limpio.