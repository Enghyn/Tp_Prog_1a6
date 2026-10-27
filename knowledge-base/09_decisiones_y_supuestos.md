# 09 - Decisiones de Diseño y Supuestos

1. **Uso de Catálogo (`estado_orden`) en lugar de CHECK**:
   - Se implementó la tabla de referencia `estado_orden` en lugar de una restricción `CHECK` estática. Esto permite asociar atributos adicionales (como `es_final`) que determinan lógicas de negocio (ej. qué constituye una orden abierta o finalizada) y facilita consultas relacionales. Las filas del catálogo se cargan mediante `seed.py`.
2. **Índices Únicos Parciales para Borrado Lógico**:
   - Para entidades con borrado lógico (`vehiculo`, `repuesto`, `asignacion_rol`), un índice `UNIQUE` común impediría registrar un nuevo ítem con la misma patente o código tras una baja. Se utilizaron índices únicos parciales con `WHERE borrado_en IS NULL` / `WHERE revocada_en IS NULL`.
3. **Gestión de Roles en Tabla Separada (`asignacion_rol`)**:
   - La entidad `usuario` no contiene una columna `rol`. Los permisos y roles se gestionan mediante asignaciones con fechas de vigencia y revocación, preservando un historial completo de auditoría sin borrar registros.
4. **Tratamiento de Seguridad en Contraseñas (Bcrypt)**:
   - Todas las operaciones con `bcrypt` se ejecutan fuera del bucle de eventos principal utilizando `asyncio.to_thread` protegido por un semáforo, evitando bloqueos del servidor ASGI y limitando la carga concurrente de hashing intensivo.
5. **Aislamiento de Escrituras de Auditoría (`intento_acceso`)**:
   - Los intentos de login se registran en su propia sesión y transacción independiente que se confirma siempre, incluso si la validación del login falla, garantizando que el intento fallido quede persistido para el conteo de seguridad (RN-08).
