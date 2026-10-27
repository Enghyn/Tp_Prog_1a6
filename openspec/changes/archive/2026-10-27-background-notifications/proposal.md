# Propuesta

## ¿Por qué?

Al terminar una orden de trabajo es necesario notificar al cliente, pero esta acción no debe bloquear la respuesta HTTP ni depender de la sesión de base de datos. Es necesario desacoplar esta notificación usando `BackgroundTasks` de FastAPI, siguiendo las restricciones del proyecto (capítulo 8 fuera de alcance, usar solo BackgroundTasks).

## ¿Qué cambios?

- **Sistema de notificaciones**: Crear `app/core/notificaciones.py` con protocolo `NotificadorCliente` e implementación `BackgroundTasksNotifier`
- **Contrato de desacoplamiento**: La tarea se agenda después del commit del Unit of Work, no recibe `AsyncSession`, solo recibe valores primitivos (ids, email, total)
- **Manejo de errores**: Las excepciones dentro de la tarea se loguean sin afectar la respuesta ya emitida
- **Simulación**: Implementar con `await asyncio.sleep(0.5)` y log estructurado

## Capacidades

### Nuevas Capacidades
- `notificaciones-background`: Notificaciones al cliente ejecutadas en segundo plano desacopladas del request

### Capacidades Modificadas
<!-- Sin capacidades existentes para modificar -->

## Impactoo

**Áreas afectadas:**
- `app/core/notificaciones.py` (nuevo)
- Uso futuro por C-19 (transiciones de órdenes)

**Dependencias:** C-01

**Notas:**
- Debe seguir el patrón de BackgroundTasks (sin Celery/Redis)
- No reutilizar sesión de base de datos
- Agendar después del commit
- Pérdida de notificación asumida si el proceso cae (documentado en KB)
