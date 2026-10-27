# 06 - Funcionalidades y Endpoints de Referencia

La API se organiza en módulos funcionales expuestos a través de grupos de rutas protegidos y abiertos.

## Módulos y Endpoints Principales

### 1. Health (`app/modules/health/`)
- `GET /health/live`: Comprobación de vida (no toca la base de datos). Código: `200`.
- `GET /health/ready`: Comprobación de preparación (`SELECT 1`). Códigos: `200`, `503` si la base no responde.

### 2. Autenticación (`app/modules/usuarios/`)
- `POST /auth/registro`: Auto-registro de clientes (crea usuario, rol CLIENTE y ficha de cliente). Códigos: `201`, `409`, `422`.
- `POST /auth/login`: Autenticación con verificación de intentos (`intento_acceso`), hash de contraseña y emisión de cookie `access_token` (`HttpOnly`, `SameSite=Lax`). Códigos: `200`, `401`, `422`, `429`.
- `POST /auth/logout`: Cierre de sesión borrando la cookie. Código: `200`.
- `GET /auth/yo`: Datos del usuario autenticado, roles vigentes y del token. Códigos: `200`, `401`.
- `POST /auth/cambiar-password`: Cambio de contraseña (invalida sesiones anteriores). Códigos: `200`, `401`, `422`.

### 3. Usuarios y Roles (`app/modules/usuarios/`)
- `POST /usuarios`: Alta de personal con contraseña provisoria (Solo `ADMIN`). Códigos: `201`, `409`, `422`.
- `GET /usuarios/{id}/roles`: Consulta de roles de un usuario (Solo `ADMIN`). Códigos: `200`, `404`.
- `POST /usuarios/{id}/roles`: Asignación de rol con vencimiento opcional (Solo `ADMIN`). Códigos: `201`, `404`, `409`, `422`.
- `DELETE /usuarios/{id}/roles/{rol}`: Revocación de rol (Solo `ADMIN`). Códigos: `200`, `404`, `409`.
- `GET /eventos`: Auditoría de seguridad con paginación (Solo `ADMIN`). Códigos: `200`, `422`.

### 4. Clientes y Vehículos (`app/modules/clientes/`)
- `POST /clientes`: Alta de cliente (Roles: `RECEPCION`, `ADMIN`). Códigos: `201`, `409`, `422`.
- `GET /clientes/{id}`: Detalle de cliente con sus vehículos (Roles: `RECEPCION`, `ADMIN`). Códigos: `200`, `404`.
- `POST /clientes/{id}/vehiculos`: Alta de vehículo para un cliente (Roles: `RECEPCION`, `ADMIN`). Códigos: `201`, `404`, `409`, `422`.
- `DELETE /vehiculos/{id}`: Borrado lógico de vehículo (Roles: `RECEPCION`, `ADMIN`). Códigos: `204`, `404`, `409`.
- `GET /mis-vehiculos`: Vehículos del cliente autenticado. Código: `200`.

### 5. Repuestos y Stock (`app/modules/repuestos/`)
- `GET /repuestos`: Listado paginado con búsqueda por descripción (`q`, `page`, `size`). Códigos: `200`, `422`.
- `GET /repuestos/{id}`: Detalle de repuesto. Códigos: `200`, `404`.
- `POST /repuestos`: Alta de repuesto con stock inicial (Solo `ADMIN`). Códigos: `201`, `409`, `422`.
- `PATCH /repuestos/{id}`: Modificación parcial de descripción y/o precio (Solo `ADMIN`). Códigos: `200`, `404`, `422`.
- `DELETE /repuestos/{id}`: Borrado lógico de repuesto (Solo `ADMIN`). Códigos: `204`, `404`.
- `POST /repuestos/{id}/reponer`: Reposición de stock (Solo `ADMIN`). Códigos: `200`, `404`, `422`.
- `GET /repuestos/{id}/movimientos`: Historial de movimientos de stock (Solo `ADMIN`). Códigos: `200`, `404`.
- `GET /repuestos/{id}/precios`: Historial de cambios de precio (Solo `ADMIN`). Códigos: `200`, `404`.

### 6. Órdenes de Trabajo (`app/modules/ordenes/`)
- `POST /ordenes`: Apertura de orden de trabajo con ítems (Roles: `RECEPCION`, `ADMIN`). Códigos: `201`, `409`, `422`.
- `GET /ordenes`: Listado de órdenes filtrado por estado con paginación. Códigos: `200`, `422`.
- `GET /ordenes/{id}`: Detalle de orden (personal o dueño del vehículo). Códigos: `200`, `403`, `404`.
- `POST /ordenes/{id}/iniciar`: Iniciar orden (Solo `MECANICO` asignado o disponible). Códigos: `200`, `404`, `409`.
- `POST /ordenes/{id}/terminar`: Terminar orden y descontar stock (Mecánico asignado o `ADMIN`). Códigos: `200`, `403`, `404`, `409`.
- `POST /ordenes/{id}/cancelar`: Cancelar orden (`RECEPCION`, `ADMIN` o dueño del vehículo). Códigos: `200`, `403`, `404`, `409`.
- `GET /estados-orden`: Consulta del catálogo de estados por posición. Código: `200`.
- `GET /mis-ordenes`: Órdenes del cliente autenticado con paginación. Códigos: `200`, `422`.
