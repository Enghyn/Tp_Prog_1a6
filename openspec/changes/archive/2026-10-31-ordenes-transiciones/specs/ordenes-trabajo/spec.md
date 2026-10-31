# Spec Delta

## ADDED Requirements

### Requirement: Inicio de orden de trabajo
El sistema SHALL permitir a un usuario autenticado con rol MECANICO, RECEPCION o ADMIN iniciar una orden en estado PENDIENTE, asignando el mecánico autenticado si la orden no tiene uno, transicionando a EN_REPARACION y registrando una línea de historial en la misma transacción. Una transición inválida MUST responder 409. Una orden inexistente MUST responder 404.

#### Scenario: Inicio exitoso asigna mecánico
- **WHEN** un mecánico autenticado invoca POST /ordenes/{id}/iniciar sobre una orden PENDIENTE sin mecánico asignado
- **THEN** responde 200 con la orden en estado EN_REPARACION y mecanico_id igual al usuario autenticado

#### Scenario: Inicio exitoso conserva mecánico existente
- **WHEN** un usuario autorizado invoca POST /ordenes/{id}/iniciar sobre una orden PENDIENTE que ya tiene mecánico asignado
- **THEN** responde 200 manteniendo el mecanico_id original y transicionando a EN_REPARACION

#### Scenario: Transición inválida
- **WHEN** se invoca POST /ordenes/{id}/iniciar sobre una orden que no está en PENDIENTE
- **THEN** responde 409

#### Scenario: Orden inexistente
- **WHEN** se invoca POST /ordenes/{id}/iniciar con un id inexistente
- **THEN** responde 404

#### Scenario: Línea de historial creada
- **WHEN** una orden se inicia exitosamente
- **THEN** existe una línea en historial_estado_orden con desde_estado PENDIENTE y hasta_estado EN_REPARACION

### Requirement: Terminación de orden con descuento atómico de stock
El sistema SHALL permitir a un usuario autorizado terminar una orden en estado EN_REPARACION, verificando stock suficiente de cada ítem, descontando repuesto.stock, registrando un movimiento_stock con cantidad negativa y motivo TERMINACION por cada ítem, transicionando a TERMINADA y agregando historial, todo en un único bloque transaccional. Si el stock es insuficiente MUST hacer rollback total y responder 409. Una transición inválida MUST responder 409. Una orden inexistente MUST responder 404.

#### Scenario: Terminación exitosa descuenta stock
- **WHEN** un usuario autorizado invoca POST /ordenes/{id}/terminar sobre una orden EN_REPARACION con stock suficiente
- **THEN** responde 200 con la orden en estado TERMINADA

#### Scenario: Terminación descuenta stock por ítem
- **WHEN** una orden se termina exitosamente
- **THEN** el stock de cada repuesto se reduce en la cantidad del ítem correspondiente

#### Scenario: Terminación genera un movimiento por ítem
- **WHEN** una orden con N ítems se termina exitosamente
- **THEN** se registran N movimientos_stock con cantidad negativa y motivo TERMINACION, uno por ítem, con orden_id de la orden

#### Scenario: Stock insuficiente hace rollback total
- **WHEN** se invoca POST /ordenes/{id}/terminar y algún ítem no tiene stock suficiente
- **THEN** responde 409 y ni el stock, ni el estado de la orden ni el historial se modifican

#### Scenario: Doble terminación
- **WHEN** se invoca POST /ordenes/{id}/terminar sobre una orden ya TERMINADA
- **THEN** responde 409

#### Scenario: Terminación de orden no en reparación
- **WHEN** se invoca POST /ordenes/{id}/terminar sobre una orden PENDIENTE o CANCELADA
- **THEN** responde 409

#### Scenario: Orden inexistente
- **WHEN** se invoca POST /ordenes/{id}/terminar con un id inexistente
- **THEN** responde 404

#### Scenario: Línea de historial de terminación
- **WHEN** una orden se termina exitosamente
- **THEN** existe una línea en historial_estado_orden con desde_estado EN_REPARACION y hasta_estado TERMINADA

### Requirement: Cancelación de orden con permisos antes de estado
El sistema SHALL evaluar los permisos de cancelación (RECEPCION, ADMIN o dueño del vehículo) **antes** de validar el estado de la orden. Un usuario sin permiso MUST responder 403 aun cuando la orden sea final o inexistente en estado. Una orden ya final MUST responder 409. Una orden inexistente MUST responder 404. La cancelación no MUST modificar stock ni movimientos. La transición válida es de un estado no final a CANCELADA.

#### Scenario: Cancelación por recepción exitosa
- **WHEN** un usuario con rol RECEPCION o ADMIN invoca POST /ordenes/{id}/cancelar sobre una orden no final
- **THEN** responde 200 con la orden en estado CANCELADA

#### Scenario: Cancelación por dueño del vehículo
- **WHEN** el dueño del vehículo de la orden invoca POST /ordenes/{id}/cancelar sobre una orden no final
- **THEN** responde 200 con la orden en estado CANCELADA

#### Scenario: Cancelar orden ajena responde 403
- **WHEN** un usuario sin rol RECEPCION/ADMIN ni dueño del vehículo invoca POST /ordenes/{id}/cancelar
- **THEN** responde 403

#### Scenario: Cancelar orden final responde 409
- **WHEN** un usuario con permiso invoca POST /ordenes/{id}/cancelar sobre una orden ya TERMINADA o CANCELADA
- **THEN** responde 409

#### Scenario: Permisos evaluados antes del estado
- **WHEN** un usuario sin permiso invoca POST /ordenes/{id}/cancelar sobre una orden final
- **THEN** responde 403 (no 409)

#### Scenario: Cancelación no toca stock
- **WHEN** una orden se cancela
- **THEN** el stock de los repuestos y los movimientos_stock no se modifican

#### Scenario: Orden inexistente
- **WHEN** se invoca POST /ordenes/{id}/cancelar con un id inexistente
- **THEN** responde 404

#### Scenario: Línea de historial de cancelación
- **WHEN** una orden se cancela exitosamente
- **THEN** existe una línea en historial_estado_orden con hasta_estado CANCELADA

### Requirement: Notificación al cliente tras terminación exitosa
El sistema SHALL agendar una notificación al cliente mediante BackgroundTasks únicamente después del commit exitoso de la terminación, pasando sólo valores primitivos (orden_id, email del cliente, total) y nunca la sesión de base de datos. Si la terminación falla o no se commitea, no MUST agendarse notificación.

#### Scenario: Notificación agendada solo después del commit
- **WHEN** la terminación de una orden se completa y commitea exitosamente
- **THEN** se agenda exactamente una tarea en BackgroundTasks

#### Scenario: No se agenda en caso de fallo
- **WHEN** la terminación falla por stock insuficiente
- **THEN** no se agenda ninguna tarea de notificación

#### Scenario: Notificación recibe solo valores primitivos
- **WHEN** se agenda la notificación
- **THEN** la tarea recibe orden_id, email y total sin instancia de AsyncSession

### Requirement: Máquina de estados de orden
El sistema SHALL definir las transiciones permitidas: PENDIENTE → EN_REPARACION (iniciar), EN_REPARACION → TERMINADA (terminar), y cualquier estado no final → CANCELADA (cancelar). Toda transición no permitida MUST responder 409. Los estados TERMINADA y CANCELADA son finales y no admiten transiciones.

#### Scenario: Estados finales no transicionan
- **WHEN** se intenta iniciar o terminar una orden en estado TERMINADA o CANCELADA
- **THEN** responde 409

#### Scenario: Solo EN_REPARACION puede terminar
- **WHEN** se intenta terminar una orden en estado PENDIENTE
- **THEN** responde 409