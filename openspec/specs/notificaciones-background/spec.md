# Especificación: notificaciones-background

## Purpose

Provee un mecanismo de notificación al cliente ejecutado en segundo plano, desacoplado del request HTTP y sin reutilizar la sesión de base de datos.

## Requirements

### Requirement: Protocolo de notificación
El sistema SHALL definir un protocolo `NotificadorCliente` con método `notificar_orden_terminada(orden_id)` y una implementación `BackgroundTasksNotifier`.

#### Scenario: Notificación con BackgroundTasks
- **CUANDO** se agenda una notificación con `BackgroundTasks`
- **ENTONCES** la tarea se ejecuta en segundo plano sin bloquear la respuesta HTTP

### Requirement: Desacoplamiento del request
La tarea SHALL ejecutarse después del commit del Unit of Work y SHALL NOT recibir una instancia de `AsyncSession`. Solo SHALL recibir valores primitivos.

#### Scenario: Notificación después del commit
- **CUANDO** se agenda la notificación después de un commit exitoso
- **ENTONCES** la tarea recibe solo valores primitivos (ids, email, total) sin sesión de BD

#### Scenario: No abre conexión a base de datos
- **CUANDO** se ejecuta la tarea de notificación
- **ENTONCES** no abre ni utiliza conexión a base de datos

### Requirement: Resiliencia ante fallos
Las excepciones dentro de la tarea de notificación SHALL ser capturadas, logueadas y SHALL NOT afectar la respuesta HTTP ya emitida.

#### Scenario: Fallo en la tarea
- **CUANDO** ocurre un error dentro de la tarea de notificación
- **ENTONCES** el error se loguea pero la respuesta HTTP ya enviada no se altera
