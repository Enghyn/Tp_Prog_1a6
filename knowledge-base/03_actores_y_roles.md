# 03 - Actores y Roles

## Actores del Sistema
1. **Anónimo / Visitante**: Usuario sin sesión autenticada. Puede acceder a rutas públicas (`/health/*`, `/auth/registro`, `/auth/login`).
2. **Cliente**: Usuario registrado con rol `CLIENTE`. Puede ver sus propios vehículos y órdenes (`/mis-vehiculos`, `/mis-ordenes`), y cancelar sus órdenes pendientes.
3. **Recepcionista**: Usuario con rol `RECEPCION`. Puede dar de alta clientes, vehículos, consultar repuestos, y abrir/gestionar órdenes de trabajo.
4. **Mecánico**: Usuario con rol `MECANICO`. Puede iniciar órdenes asignadas (`/ordenes/{id}/iniciar`), terminarlas (`/ordenes/{id}/terminar`) y consultar repuestos y órdenes.
5. **Administrador**: Usuario con rol `ADMIN`. Tiene privilegios completos: reponer stock, modificar precios de repuestos, asignar/revocar roles de personal, dar de baja elementos, y terminar cualquier orden.
6. **Sistema (`SISTEMA`)**: Actor textual especial utilizado en registros de auditoría y seguridad (`evento_seguridad`) para marcar acciones automáticas (ej. carga inicial de `seed.py`).

## Gestión de Roles y Autenticación
- **Tabla Propia (`asignacion_rol`)**: La tabla `usuario` no contiene una columna `rol`. Los roles vigentes se determinan consultando la tabla `asignacion_rol` filtrando por `revocada_en IS NULL` y (si existe) `vence_en > NOW()`.
- **Vigencia y Revocación**: Revocar un rol establece `revocada_en = NOW()` sin borrar la fila, manteniendo el historial completo de auditoría. Reasignar un rol vencido cierra la anterior y abre una nueva fila.
- **Autoprotección (RN-05)**: Un administrador no puede revocar su propio rol `ADMIN`, y el sistema nunca puede quedar sin administradores vigentes.
- **Autorización por Petición (RN-04)**: Los permisos se verifican consultando los roles vigentes en la base de datos en cada petición protegida. Los roles contenidos en el token JWT son meramente informativos.
