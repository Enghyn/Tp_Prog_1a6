# Design

## Context

El módulo `app/modules/ordenes/` (C-18) ya define modelos, repositorios, UoW, servicio y router para apertura y consulta. `EstadoOrden` incluye `es_final` y `posicion`; las transiciones válidas son PENDIENTE → EN_REPARACION → TERMINADA, y CANCELADA es final. `MovimientoStock` y `HistorialEstadoOrden` son append-only (RN-15, triggers). `Repuesto.stock` tiene CHECK `>= 0`. El módulo de notificaciones (C-04) expone `BackgroundTasksNotifier` con `notificar_orden_terminada(orden_id, email, total)`. Ver `proposal.md` para la motivación.

## Goals / Non-Goals

**Goals:**
- Implementar inicio, terminación atómica con descuento de stock y cancelación con permisos evaluados antes del estado.
- Garantizar rollback total si el stock es insuficiente.
- Agendar la notificación al cliente sólo después del commit exitoso de `terminar`, pasando sólo valores primitivos.

**Non-Goals:**
- Concurrencia avanzada / bloqueos (cap. 7, fuera de alcance).
- Entrega real de email (simulación con `asyncio.sleep(0.5)`).
- C-20 verificación E2E.

## Decisions

1. **Máquina de estados en el servicio**: helper `transicion_valida(desde, hasta)` que define las transiciones permitidas (PENDIENTE→EN_REPARACION, EN_REPARACION→TERMINADA, no-final→CANCELADA). Cualquier otra transición lanza `ConflictoError` (409). Los estados finales (TERMINADA, CANCELADA) no admiten transiciones.

2. **`iniciar_orden(uow, orden_id, usuario_id)`**:
   - Obtener la orden con precarga (`uow.ordenes.get_by_id`); 404 si no existe.
   - Validar transición PENDIENTE→EN_REPARACION; 409 si inválida.
   - Si `mecanico_id is None`, asignar `usuario_id`.
   - Actualizar `estado = EN_REPARACION`.
   - Crear `HistorialEstadoOrden(desde=PENDIENTE, hasta=EN_REPARACION, usuario_id, cuando=now)`.
   - Persistir vía `uow.ordenes.update` y `uow.historial.add`.
   - Devolver la orden recargada.

3. **`terminar_orden(uow, orden_id, usuario_id)`**:
   - Obtener la orden con precarga de `items.repuesto`; 404 si no existe.
   - Validar transición EN_REPARACION→TERMINADA; 409 si inválida.
   - **Pre-check de stock**: para cada ítem, verificar `repuesto.stock >= item.cantidad`; si alguno no alcanza, lanzar `ConflictoError` (409) ANTES de mutar. Como la excepción se propaga antes de cualquier `update`/`add`, el UoW hace rollback al salir del handler.
   - Mutar en el mismo UoW, ítem por ítem: `repuesto.stock -= cantidad`; `uow.repuestos...` (el `Repuesto` se actualiza vía `uow.session` reutilizando el modelo, sin abrir segundo UoW); crear `MovimientoStock(repuesto_id, orden_id, usuario_id, cantidad=-cantidad, motivo=TERMINACION, cuando=now)`.
   - Actualizar `estado = TERMINADA`.
   - Crear `HistorialEstadoOrden(desde=EN_REPARACION, hasta=TERMINADA, usuario_id, cuando=now)`.
   - Commit lo hace el router tras el servicio (`await uow.commit()`). La notificación se agenda en el router **después** del commit.
   - Devolver la orden recargada.

   Nota: no se abre un segundo UoW para repuestos; se opera sobre `uow.session` directamente reutilizando `Repuesto` y `MovimientoStock` (mismo patrón que `crear_orden` con `Repuesto`). Esto mantiene una sola transacción (RN-13).

4. **`cancelar_orden(uow, orden_id, usuario_id)`**:
   - **Permisos PRIMERO** (RN-12): obtener la orden (404 si no existe). Luego evaluar: RECEPCION/ADMIN (roles vigentes) OR dueño del vehículo (`es_duenio_de_orden`). Si no cumple → `ProhibidoError` (403). El mecánico asignado NO tiene permiso de cancelar (RN-12 lo limita a recepción/admin/dueño).
   - **Estado DESPUÉS**: si `estado.es_final` → `ConflictoError` (409). Si la transición no-final→CANCELADA no es válida (ya final) → 409.
   - Actualizar `estado = CANCELADA`.
   - Crear `HistorialEstadoOrden(desde=estado_anterior, hasta=CANCELADA, usuario_id, cuando=now)`.
   - No toca stock ni movimientos.
   - Devolver la orden recargada.

   Orden de validación: existencia (404) → permiso (403) → estado final (409). Esto coincide con "permisos antes de estado": un usuario sin permiso sobre una orden final recibe 403, no 409.

5. **Notificación tras terminar**: el router `terminar` recibe `background_tasks: BackgroundTasks`. Tras `await uow.commit()`, resuelve el email del cliente y el total:
   - Recargar la orden (ya con precarga) → `orden.vehiculo.cliente_id` → consultar `Cliente.usuario_id` → `Usuario.email`.
   - `notifier = BackgroundTasksNotifier(background_tasks)`; `notifier.notificar_orden_terminada(orden_id=orden.id, email=email, total=float(orden.total))`.
   - Alternativa: resolver el email dentro del servicio y devolverlo. Decisión: el servicio `terminar_orden` devuelve la orden; el router resuelve el email con una consulta adicional sobre la misma sesión ya commiteada (la sesión sigue abierta; `expire_on_commit=False`). O, más simple, el servicio devuelve también el email. Decisión final: el servicio devuelve `(orden, email_cliente)` para evitar una segunda consulta y mantener la notificación desacoplada. El router usa esos valores para agendar.

   Nota: la sesión sigue disponible tras commit (no se cierra). Pero para respetar "sólo valores, nunca la sesión", el router sólo pasa `orden.id`, `email`, `total` al notifier.

6. **RBAC de endpoints**:
   - `POST /ordenes/{id}/iniciar`: autenticado; autorización fina en servicio (RECEPCION/ADMIN/MECANICO). Usar `obtener_usuario_actual`.
   - `POST /ordenes/{id}/terminar`: autenticado; autorización fina en servicio (RECEPCION/ADMIN/MECANICO asignado). Usar `obtener_usuario_actual`.
   - `POST /ordenes/{id}/cancelar`: autenticado; permisos en servicio (RECEPCION/ADMIN/dueño). Usar `obtener_usuario_actual`.

   Para iniciar/terminar, cualquier MECANICO/RECEPCION/ADMIN puede operar (el alcance no restringe por asignación). El cancelar sí restringe.

7. **Respuesta**: los tres endpoints devuelven `OrdenRead` con 200.

8. **Precarga**: `OrdenRepository.get_by_id` ya precarga `vehiculo`, `items.repuesto`, `mecanico`. En `terminar`, se itera `orden.items` accediendo `item.repuesto` (precargado, sin N+1).

9. **Manejo de stock insuficiente**: pre-check antes de mutar; si falla, se lanza antes de cualquier `flush` de mutación. Como el handler no llama `uow.commit()` (la excepción aborta), el `__aexit__` del UoW no aplica aquí porque el router llama `uow.commit()` manualmente sólo en éxito. Importante: el router debe envolver en try/except o usar `async with uow`? El patrón actual es manual: servicio muta (con flush), router llama `await uow.commit()`. Si el servicio lanza antes de mutar, no hay commit. Si muta parcialmente y luego falla, habría commit parcial. Por eso el pre-check completo se hace ANTES de cualquier mutación, y la mutación se hace en bloque sin posibilidad de fallo de negocio (sólo flush). Así el rollback de la sesión externa (test) limpia todo. Además, en producción, si un flush falla, la excepción aborta antes del commit. Bueno.

   Sin embargo, el test "stock insuficiente 409 con stock y estado intactos" depende de que no se commitee. Como el router no llama commit al lanzar, y `get_session` cierra la sesión al final sin commit (rollback implícito al cerrar? Actually SQLAlchemy async session close rolls back uncommitted). En tests con `contexto_auth`, el override commitea al final del request (`await session.commit()`). Wait, el override `override_get_session` hace `async with session_factory() as session: yield session; await session.commit()`. So even on exception? The `await session.commit()` is after yield, runs in finally? No, it's in the generator after yield, which runs on cleanup. If an exception occurs, the generator is closed via throw, so the `await session.commit()` line may not execute; instead the session is closed with pending changes rolled back. Actually FastAPI handles dependency cleanup: on exception, it throws into the generator, so code after yield won't run normally; the session context manager __aexit__ rolls back. Good. So uncommitted changes roll back. 

   Pero el servicio llama `uow.session.flush()` (e.g., add movimiento). Those are pending in the session. On rollback, discarded. Good.

10. **Transacciones y commit**: el router llama `await uow.commit()` sólo si el servicio retorna sin excepción. La notificación se agenda después.

11. **Resolución del email del cliente**: dentro de `terminar_orden`, después de mutar pero antes de retornar, consultar `Cliente` por `vehiculo.cliente_id`, luego `Usuario` por `cliente.usuario_id`, obtener `email`. Devolver `(orden, email)`.

## Risks / Trade-offs

- [Pre-check vs mutación no atómica en concurrencia] → fuera de alcance (cap. 7). Se acepta.
- [N+1 en terminar] → `get_by_id` precarga `items.repuesto`; se itera sobre la colección precargada.
- [Notificación agendada antes del commit] → se agenda en el router después de `await uow.commit()`, nunca dentro del servicio.
- [Sesión reutilizada para repuestos sin segundo UoW] → mismo patrón que `crear_orden`; mantiene una sola transacción.
- [Mecánico sin permiso de cancelar] → RN-12 limita a recepción/admin/dueño; documentado.

## Migration Plan

Sin migración Alembic. Desplegar código. Rollback: revertir commit.

## Open Questions

- Código HTTP de éxito para las transiciones: se asume 200 con `OrdenRead` (consistente con `reponer_stock`). Si los tests esperan 204 para cancelar, ajustar en apply.
- Si `iniciar`/`terminar` deben restringir por mecánico asignado: el alcance no lo exige; se permite a cualquier MECANICO/RECEPCION/ADMIN.