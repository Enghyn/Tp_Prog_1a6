# 05 - Reglas de Negocio (RN-01 a RN-20)

| Regla | Enunciado resumido | Garante / Mecanismo esperado | Código HTTP |
| :--- | :--- | :--- | :--- |
| **RN-01** | Unicidad de correo, documento, patente (vigente) y código de repuesto (vigente). | UNIQUE / Índices únicos parciales en base de datos. | 409 (Conflict) |
| **RN-02** | El auto-registro crea usuario, rol CLIENTE y ficha de cliente en una sola transacción. | Unit of Work atómico. | 409 / 201 |
| **RN-03** | Un usuario tiene a lo sumo una asignación abierta por rol. | Índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL`. | 409 |
| **RN-04** | Permisos decididos por roles vigentes en base de datos en cada petición. | Dependencia que consulta `asignacion_rol`. | 401 / 403 |
| **RN-05** | Un administrador no puede revocar su propio rol ADMIN ni dejar el sistema sin admins. | Validación en servicio. | 409 |
| **RN-06** | Contraseña pendiente de cambio: sólo permite rutas `/auth` y `/health`. | Dos grupos de rutas en `main.py`. | 403 |
| **RN-07** | Cambio de contraseña invalida sesiones anteriores comparando `iat` con `password_cambiada_en`. | Verificación sin truncar fracciones de segundo. | 401 |
| **RN-08** | Límite de intentos de login: 5 fallos en 60 segundos bloquean temporalmente. | Conteo en `intento_acceso` con `Retry-After`. | 429 |
| **RN-09** | Login opaco: responde igual y tarda lo mismo exista o no el correo. | Verificación contra hash ficticio si el usuario no existe. | 401 |
| **RN-10** | Orden nace PENDIENTE con ítems sin repetir; precio copiado y total calculado por servidor. | DTO de entrada estricto; precio nunca viaja en el cuerpo. | 201 / 422 |
| **RN-11** | Transiciones de estado de orden permitidas y controladas. | Lógica de servicio. | 409 |
| **RN-12** | Cancelación permitida a recepción, admin o dueño del vehículo (evaluado antes de validar estado). | Orden de validación en servicio. | 403 / 409 |
| **RN-13** | Terminar orden descuenta stock, genera movimientos e historial en un solo bloque atómico. | Unit of Work atómico; rollback si stock insuficiente. | 409 / 200 |
| **RN-14** | Stock de repuesto sólo cambia vía movimientos (alta, reposición, terminación). No por PATCH. | Punto único de escritura de stock. | 400 / 422 |
| **RN-15** | Tablas de historial y movimientos son de sólo agregado. | Trigger en PostgreSQL instalado por migración. | 500 (DB) |
| **RN-16** | Elementos dados de baja no se usan en órdenes nuevas. Vehículos con órdenes abiertas no se dan de baja. | Validación en servicio y `es_final` en catálogo. | 409 |
| **RN-17** | Rol propio: cliente ve sólo sus vehículos y órdenes. | Rutas `/mis-*` y comprobación de propiedad. | 403 |
| **RN-18** | Errores internos de BD traducidos; no se expone traza ni esquema al cliente. | Traducción de `IntegrityError` y validación de contratos. | 400 / 409 / 422 |
| **RN-19** | Estados de orden leídos del catálogo `estado_orden`. Catálogo vacío da error en creación de orden. | Clave foránea y repositorio de sólo lectura. | 409 |
| **RN-20** | Cambio de precio de repuesto genera línea en historial en la misma transacción. PATCH sin cambio no genera línea. | Unit of Work y constraint `precio_nuevo > precio_anterior`. | 200 / 409 |
