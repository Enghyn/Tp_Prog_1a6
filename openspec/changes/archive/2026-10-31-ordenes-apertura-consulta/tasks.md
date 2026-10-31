# Tasks

## 1. Scaffolding

- [x] 1.1 Agregar la relación ORM `repuesto` a `ItemOrden` en `app/modules/ordenes/models.py` (unidireccional, `lazy="raise"`) y verificar `python -c "from app.modules.ordenes.models import *"` succeeds.
- [x] 1.2 Crear `app/modules/ordenes/repository.py` con `OrdenRepository`, `ItemOrdenRepository`, `EstadoOrdenRepository` (solo lectura, sin `update`/`delete`) y `HistorialEstadoOrdenRepository` (solo `add`, sin `update`/`delete`), más `es_duenio_de_orden` existente, y verificar import succeeds.
- [x] 1.3 Crear `app/modules/ordenes/unit_of_work.py` con `OrdenesUnitOfWork` exponiendo `ordenes`, `items`, `estados`, `historial`, y verificar import succeeds.
- [x] 1.4 Crear `app/modules/ordenes/schemas.py` con `ItemOrdenCreate`, `OrdenCreate`, `ItemOrdenRead`, `OrdenRead`, `EstadoOrdenRead` (`extra="forbid"` donde corresponda) y verificar import succeeds.

## 2. Service implementation (TDD)

- [x] 2.1 Write failing tests for apertura exitosa con total calculado en servidor y precio copiado del catálogo; implementar `crear_orden`; verify tests pass.
- [x] 2.2 Write failing tests para entrada estricta (precio/total en cuerpo → 422, ítem repetido → 422, cantidad ≤ 0 → 422, sin ítems → 422); implementar validaciones; verify tests pass.
- [x] 2.3 Write failing tests para repuesto dado de baja → 409 y repuesto inexistente → 404; implementar validación de repuestos vigentes; verify tests pass.
- [x] 2.4 Write failing tests para catálogo de estados vacío → 409 (RN-19); implementar verificación `count() == 0` y estado inicial 'PENDIENTE'; verify tests pass.
- [x] 2.5 Write failing tests para línea inicial de historial (`desde_estado=NULL → PENDIENTE`); implementar creación en el mismo UoW; verify tests pass.
- [x] 2.6 Write failing tests para `GET /ordenes/{id}`: detalle con precarga, 404 inexistente, 403 sin permiso (ajeno); implementar `obtener_orden` con autorización; verify tests pass.
- [x] 2.7 Write failing tests para `GET /ordenes`: filtro por estado y paginación; implementar `listar_ordenes`; verify tests pass.
- [x] 2.8 Write failing tests para `GET /mis-ordenes`: solo órdenes del cliente autenticado; implementar `mis_ordenes`; verify tests pass.
- [x] 2.9 Write failing tests para `GET /estados-orden` ordenado por `posicion`; implementar `listar_estados`; verify tests pass.

## 3. Router and mounting

- [x] 3.1 Crear `app/modules/ordenes/router.py` con los 5 endpoints aplicando RBAC y precarga; montar en `main.py` (`router_protegido`); verificar que la app arranca y OpenAPI lista las rutas.
- [x] 3.2 Write integration tests para RBAC (POST solo RECEPCION/ADMIN; GET /ordenes RECEPCION/MECANICO/ADMIN; /mis-ordenes solo CLIENTE; /estados-orden autenticado) y verificar pytest pasa.

## 4. Verification

- [x] 4.1 Ejecutar `pytest -q` (suite completa) y `alembic check` (sin migraciones pendientes) y verificar que todo pasa.
- [x] 4.2 Verificar contratos HTTP: respuestas `{"detail", "codigo"}` en errores y `Page` con `page`/`size` en listados.

## Workflow follow-up

- Archivar el change tras revisar los requisitos.
