# 10 - Preguntas Abiertas y Limitaciones Deliberadas

1. **Concurrencia y Actualizaciones Perdidas (Capítulo 7)**:
   - *Decisión*: El sistema actual utiliza el nivel de aislamiento por defecto de PostgreSQL. Dos órdenes que terminen simultáneamente podrían leer el mismo stock y descontar sobre él (actualización perdida potencial sin bloqueo pesimista/optimista). Esto queda fuera del alcance académico actual y será abordado en el Capítulo 7.
2. **Colas de Tareas Distribuidas (Capítulo 8)**:
   - *Decisión*: El aviso al cliente al terminar una orden se implementa mediante `BackgroundTasks` de FastAPI, ejecutándose en el mismo proceso. Si el servidor se reinicia durante la tarea asincrónica, el aviso se pierde sin reintento automático. Esto se acepta para el alcance actual y se resolvió formalmente con colas basadas en Redis en etapas posteriores.
3. **Rol Único de Base de Datos**:
   - *Decisión*: La conexión a PostgreSQL se realiza con un único usuario de base de datos. Los mecanismos de seguridad de sólo agregado se basan en disparadores (`TRIGGERS`) a nivel de base de datos (`RN-15`) en lugar de restricciones de permisos por rol de base de datos, cumpliendo con la defensa en profundidad requerida.
