# Proposal

## Why

El módulo `app/modules/ordenes/` permite abrir y consultar órdenes de trabajo, pero no existen endpoints ni lógica para iniciar, terminar ni cancelar una orden. Sin ellos el ciclo de vida de la orden queda incompleto y no se consume stock al terminar (RN-13), ni se valida la máquina de estados (RN-11) ni los permisos de cancelación (RN-12). Además, al terminar una orden se debe notificar al cliente en segundo plano (C-04) desacoplando la notificación del commit.

## What Changes

- Tres nuevos endpoints en el router de órdenes: `POST /ordenes/{id}/iniciar`, `POST /ordenes/{id}/terminar`, `POST /ordenes/{id}/cancelar`.
- `iniciar`: asigna el mecánico autenticado si la orden no tiene uno, transición `PENDIENTE → EN_REPARACION`, línea de historial; transición inválida → 409 (RN-11).
- `terminar`: UoW único que verifica stock de cada ítem, descuenta `repuesto.stock`, registra `movimiento_stock` (cantidad negativa, motivo `TERMINACION`) por ítem, pasa a `TERMINADA` y agrega historial; stock insuficiente → rollback total + 409 (RN-13).
- `cancelar`: evalúa permisos (RECEPCION / ADMIN / dueño del vehículo) **antes** de validar el estado → 403 si no corresponde, 409 si ya es final; no toca stock (RN-12).
- Tras el commit exitoso de `terminar`, agenda `NotificadorCliente` en `BackgroundTasks` pasando sólo valores primitivos, nunca la sesión (C-04).
- Métodos de servicio correspondientes (`iniciar_orden`, `terminar_orden`, `cancelar_orden`) y validación de transiciones.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ordenes-trabajo`: se agregan las transiciones de estado (inicio, terminación con descuento atómico de stock y cancelación), la máquina de estados (RN-11), los permisos de cancelación (RN-12) y la notificación al cliente en segundo plano tras la terminación.

## Impact

- Código: `app/modules/ordenes/service.py` (nuevos métodos), `app/modules/ordenes/router.py` (3 endpoints), `app/modules/ordenes/schemas.py` (posibles respuestas).
- APIs: 3 nuevos endpoints bajo `/ordenes/{id}`.
- Dependencias: C-04 (background-notifications) y C-18 (ordenes-apertura-consulta) archivadas. Reutiliza `Repuesto`/`MovimientoStock` de `app/modules/repuestos/`.
- Sin cambios de esquema ni migraciones Alembic.
- Governance: CRÍTICO. Strict TDD.