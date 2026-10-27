# Delta de Especificación

## Propósito

Provee un mecanismo de notificación al cliente ejecutado en segundo plano, desacoplado del request HTTP y sin reutilizar la sesión de base de datos.

## REQUISITOS AGREGADOS

### Requisito: Protocolo de notificación
El sistema DEBE definir un protocolo `NotificadorCliente` con método `notificar_orden_terminada(orden_id)` y una implementación `BackgroundTasksNotifier`.

#### Escenario: Notificación con BackgroundTasks
- **CUANDO** se agenda una notificación con `BackgroundTasks`
- **ENTONCES** la tarea se ejecuta en segundo plano sin bloquear la respuesta HTTP

### Requisito: Desacoplamiento del request
La tarea DEBE ejecutarse después del commit del Unit of Work y NO DEBE recibir una instancia de `AsyncSession`. Solo debe recibir valores primitivos.

#### Escenario: Notificación después del commit
- **CUANDO** se agenda la notificación después de un commit exitoso
- **ENTONCES** la tarea recibe solo valores primitivos (ids, email, total) sin sesión de BD

#### Escenario: No abre conexión a base de datos
- **CUANDO** se ejecuta la tarea de notificación
- **ENTONCES** no abre ni utiliza conexión a base de datos

### Requisito: Resiliencia ante fallos
Las excepciones dentro de la tarea de notificación DEBEN ser capturadas, logueadas y NO DEBEN afectar la respuesta HTTP ya emitida.

#### Escenario: Fallo en la tarea
- **CUANDO** ocurre un error dentro de la tarea de notificación
- **ENTONCES** el error se loguea pero la respuesta HTTP ya enviada no se altera
