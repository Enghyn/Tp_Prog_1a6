# Tasks

## 1. Baseline y scaffolding

- [x] 1.1 Ejecutar `pytest -q` sobre la suite existente y verificar que está verde antes de tocar código (safety-net baseline).
- [x] 1.2 Verificar imports de `BackgroundTasksNotifier`, `MovimientoStock`, `Repuesto`, `Cliente`, `Usuario` y `es_duenio_de_orden` desde los módulos existentes; verificar `python -c "from app.modules.ordenes.service import *"` succeed.

## 2. Máquina de estados y `iniciar_orden` (TDD)

- [x] 2.1 Write failing tests para `iniciar`: éxito PENDIENTE→EN_REPARACION asignando mecánico si null, conservando mecánico existente, línea de historial creada, transición inválida → 409, orden inexistente → 404; implementar `iniciar_orden` y helper `transicion_valida`; verify tests pass.
- [x] 2.2 Agregar endpoint `POST /ordenes/{orden_id}/iniciar` (autenticado, `obtener_usuario_actual`) delegando en `iniciar_orden` y `await uow.commit()`; verificar que la app arranca y OpenAPI lista la ruta.

## 3. `terminar_orden` con descuento atómico de stock (TDD)

- [x] 3.1 Write failing tests para terminación exitosa: respuesta 200 con estado TERMINADA, stock descontado por ítem, un movimiento_stock por ítem (cantidad negativa, motivo TERMINACION, orden_id), línea de historial EN_REPARACION→TERMINADA; implementar `terminar_orden`; verify tests pass.
- [x] 3.2 Write failing tests para fallos de terminación: stock insuficiente → 409 con stock y estado intactos, doble terminar → 409, terminar orden no EN_REPARACION → 409, orden inexistente → 404; implementar guards (pre-check de stock antes de mutar); verify tests pass.
- [x] 3.3 Agregar endpoint `POST /ordenes/{orden_id}/terminar` con parámetro `background_tasks: BackgroundTasks`, llamando `terminar_orden` (que devuelve orden y email del cliente), `await uow.commit()` y luego agendando `BackgroundTasksNotifier.notificar_orden_terminada(orden_id, email, total)` sólo después del commit; verify tests pass.
- [x] 3.4 Write test de notificación: parchear `BackgroundTasksNotifier` para capturar llamadas y verificar que se agenda exactamente una tarea tras commit exitoso y ninguna en caso de stock insuficiente; verify test pass.

## 4. `cancelar_orden` con permisos antes de estado (TDD)

- [x] 4.1 Write failing tests para cancelación: éxito por RECEPCION/ADMIN/dueño del vehículo → 200 CANCELADA, 403 orden ajena, 409 orden final, 403 antes de 409 (permisos evaluados primero), sin cambios en stock/movimientos, 404 inexistente, línea de historial creada; implementar `cancelar_orden`; verify tests pass.
- [x] 4.2 Agregar endpoint `POST /ordenes/{orden_id}/cancelar` (autenticado) delegando en `cancelar_orden` y `await uow.commit()`; verificar RBAC y OpenAPI.

## 5. Verificación de integración

- [x] 5.1 Ejecutar `pytest -q` (suite completa) y verificar que todo pasa sin warnings de sesión abierta.
- [x] 5.2 Verificar contratos HTTP: errores con body `{"detail", "codigo"}`, respuestas 200 con `OrdenRead` en transiciones, y `alembic check` sin migraciones pendientes.
- [x] 5.3 Refactor verification: revisar que no haya N+1 en terminar (precarga `items.repuesto`), que no se commitee en repositorios, y que los handlers sean `async def`.

## Workflow follow-up

- Archivar el change tras revisar los requisitos (`/opsx:archive ordenes-transiciones`) y marcar `[x]` en CHANGES.md.