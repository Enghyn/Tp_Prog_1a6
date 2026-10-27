# Diseño

## Contextoo

C-01 y C-02 están completos. Se necesita notificar al cliente al terminar una orden (usado por C-19). Debe ser asíncrono y desacoplado.

## Objetivos / No Objetivos

**Objetivos:**
- Crear protocolo para notificaciones
- Implementar con BackgroundTasks de FastAPI
- Garantizar desacoplamiento de la sesión
- Manejo resiliente de errores

**No Objetivos:**
- Implementar colas distribuidas (Redis/Celery) - fuera de alcance
- Implementar envío real de emails/SMS
- Implementar lógica de órdenes

## Decisiones

### Decisión 1: Usar BackgroundTasks
**Opción elegida:** `fastapi.BackgroundTasks`
**Justificación:** Solo está permitido usar BackgroundTasks según KB. Celery/Redis están fuera de alcance.

### Decisión 2: Pasar solo valores primitivos
**Opción elegida:** La tarea recibe `orden_id`, `email`, `total` etc., nunca objetos de ORM ni `AsyncSession`
**Justificación:** Evita usar sesión ya cerrada después del commit

### Decisión 3: Agendar después del commit
**Opción elegida:** El servicio agenda la tarea después de que el UoW haga commit exitosamente
**Justificación:** Garantiza que la orden está persistida antes de notificar

### Decisión 4: Capturar excepciones en la tarea
**Opción elegida:** Try/except dentro de la tarea con logging
**Justificación:** La respuesta ya fue enviada, el error no debe afectarla

## Riesgos / Compromisos

- **Riesgo:** Pérdida de notificaciones si el proceso muere → **Mitigación:** Aceptado y documentado (KB 10_preguntas_abiertas)
- **Riesgo:** Tareas en memoria se pierden al reiniciar → **Mitigación:** Aceptado por restricciones del proyecto
- **Compromiso:** Simplicidad vs fiabilidad, acorde al alcance del TP
