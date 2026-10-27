# Tareas

## 1. Módulo de notificaciones
- [x] 1.1 Crear `app/core/notificaciones.py` con protocolo `NotificadorCliente` y clase `BackgroundTasksNotifier` con método `notificar_orden_terminada` - Verificar: protocolo y clase definidos correctamente
- [x] 1.2 Implementar la tarea con `await asyncio.sleep(0.5)` y log estructurado - Verificar: simulación funciona
- [x] 1.3 Añadir manejo de excepciones dentro de la tarea (log y no propagar) - Verificar: errores no afectan flujo

## 2. Pruebas
- [x] 2.1 Crear pruebas: tarea se ejecuta y loguea, no abre conexión a base, fallo en tarea no altera respuesta 200 - Verificar: todas las pruebas pasan
- [x] 2.2 Verificar que la tarea recibe solo valores primitivos - Verificar: firma acepta valores simples
