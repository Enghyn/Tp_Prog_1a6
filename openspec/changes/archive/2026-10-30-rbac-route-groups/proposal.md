# Proposal

## Why

Después de C-09 la API sabe *quién* es el usuario (`obtener_usuario_actual`), pero todavía no sabe *qué puede hacer*: no existe una dependencia que decida permisos a partir de los roles vigentes en `asignacion_rol`, no hay forma de exigir roles por router, y todas las rutas están montadas en un único grupo sin distinguir públicas de protegidas. Eso deja sin implementar RN-04 (los roles del JWT son informativos), RN-06 (contraseña pendiente sólo accede a `/auth/*` y `/health/*`) y RN-17 (el cliente sólo ve lo suyo), y bloquea a C-12 y a todos los módulos de dominio, que necesitan `require_roles` y los helpers de propiedad para declarar sus permisos.

## What Changes

- **`get_roles_vigentes(usuario_id)`** en `app/core/dependencies.py`: consulta `asignacion_rol` en **cada request** con `revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`. Los `roles` del JWT se ignoran para decidir (RN-04).
- **`require_roles(*roles)`** como *factory* de dependencias reutilizable por router: sin credencial válida → `401`, credencial válida sin ninguno de los roles pedidos → `403`.
- **Helpers de propiedad** `es_duenio_de_vehiculo(usuario_id, vehiculo_id)` y `es_duenio_de_orden(usuario_id, orden_id)` para que los endpoints `/mis-*` y la cancelación por dueño apliquen RN-17 sin duplicar SQL.
- **Dos grupos de rutas en `main.py`**: `router_publico` (`/health/*`, `/auth/registro`, `/auth/login` y `/auth/logout`, que por contrato de C-09 responde `200` sin sesión) y `router_protegido` (todo el resto, incluido `/auth/yo`), de modo que la autenticación sea el *default* y lo público la excepción declarada.
- **Gating de `debe_cambiar_password`** (RN-06): un usuario con contraseña provisoria recibe `403` en cualquier ruta del grupo protegido, y sigue pudiendo usar `/auth/*` (incluido el futuro `POST /auth/cambiar-password` de C-11) y `/health/*`.
- **`GET /auth/yo`** pasa a consumir `get_roles_vigentes` en lugar de filtrar la colección precargada en Python. El contrato HTTP no cambia.
- **Tests de integración** en `tests/` contra PostgreSQL real: rol revocado en caliente pierde acceso en la request siguiente, `vence_en` pasado no autoriza, `401` vs `403` correctos, y usuario con contraseña pendiente bloqueado en dominio y habilitado en `/auth/*`.

## Capabilities

### New Capabilities

- `autorizacion-rbac`: decisión de permisos por roles vigentes leídos de la base en cada petición, exigencia de roles por router, verificación de propiedad de recursos (RN-17), separación entre grupo público y protegido, y bloqueo de rutas de dominio cuando la contraseña está pendiente de cambio (RN-06).

### Modified Capabilities

<!-- Ninguna: el comportamiento observable de `autenticacion-sesion` no cambia. `GET /auth/yo`
     sigue devolviendo los roles vigentes y el mismo cuerpo; sólo cambia la implementación
     (consulta SQL reutilizable en lugar de filtro en Python). -->

## Impact

**Código afectado**

- `app/core/dependencies.py`: nuevas `get_roles_vigentes`, `require_roles`, `es_duenio_de_vehiculo`, `es_duenio_de_orden` y la dependencia de gating de contraseña pendiente.
- `main.py`: se reemplaza el montaje plano por `router_publico` / `router_protegido`; el router de `usuarios` se parte en dos routers (público y autenticado) sin cambiar paths ni contratos.
- `app/modules/usuarios/router.py`: separación en `router_publico` (`/auth/login`, `/auth/logout`) y `router_autenticado` (`/auth/yo`); `GET /auth/yo` consume `get_roles_vigentes`.
- `app/modules/usuarios/service.py`: `obtener_roles_vigentes` (filtro en Python) queda como detalle interno del login o se reemplaza por la consulta SQL, según design.
- `tests/`: nueva suite `test_autorizacion_rbac.py` (y ajustes a `tests/conftest.py` si hace falta un router de prueba que declare `require_roles`).

**APIs**

- Sin cambios de path, de schema de entrada ni de cuerpo de respuesta en los endpoints existentes.
- Nuevos códigos observables en endpoints protegidos: `403` por rol faltante y `403` por contraseña pendiente. Ambos usan el formato uniforme `{"detail", "codigo"}`.

**Dependencias y datos**

- Depende de C-09 (`auth-login-jwt`, archivado): `obtener_usuario_actual`, cookie `access_token`, `SesionActual`.
- **Sin migración de base de datos**: `asignacion_rol` ya tiene `usuario_id`, `rol`, `revocada_en`, `vence_en`, y el índice parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL` sirve a la consulta.
- Sin configuración nueva.

**Fuera de alcance**

- `POST /auth/cambiar-password` (C-11) — este change sólo *bloquea* rutas cuando la bandera está activa.
- Alta de personal, asignación/revocación de roles y auditoría `GET /eventos` (C-12).
- Endpoints de dominio de clientes, vehículos, repuestos y órdenes, incluidos `/mis-vehiculos` y `/mis-ordenes` (C-15, C-16, C-18). Acá sólo se entregan los helpers que esos changes consumirán.
- Jerarquía `BaseRepository` / `UnitOfWork` (C-13, C-14).
- Revocación server-side de tokens o lista negra: el modelo sigue siendo *stateless*.
