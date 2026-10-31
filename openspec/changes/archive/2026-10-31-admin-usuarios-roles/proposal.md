# Proposal

## Why

Después de C-10 la API sabe *exigir* roles (`require_roles("ADMIN")`), pero no existe ninguna ruta que administre el personal: los usuarios sólo nacen desde `seed.py`, las asignaciones de rol sólo las escribe el seed y `evento_seguridad` se escribe pero nunca se lee. Un `ADMIN` no puede dar de alta a un empleado, otorgarle o revocarle un rol, ni auditar qué pasó en el sistema sin entrar a la base con un cliente SQL.

## What Changes

- Nuevo `POST /usuarios` (sólo `ADMIN`): alta de personal con contraseña provisoria (`debe_cambiar_password=True`, hash bcrypt fuera del event loop). Responde `201`; `409` si el email ya existe; `422` si el contrato no cumple (campos extra, email inválido, contraseña débil). Registra `USUARIO_CREADO`.
- Nuevo `GET /usuarios/{id}/roles` (sólo `ADMIN`): historial completo de asignaciones del usuario, vigentes y revocadas, ordenado por `desde` descendente. `200`; `404` si el usuario no existe.
- Nuevo `POST /usuarios/{id}/roles` (sólo `ADMIN`): asignación de rol con `desde = now()`, `vence_en` opcional futuro y `otorgada_por` = administrador autenticado. `201`; `404` si el usuario no existe; `409` si ya tiene una asignación vigente de ese rol (RN-03); `422` si el rol no pertenece al catálogo o `vence_en` no es futuro. Una asignación **vencida** se cierra (`revocada_en = now()`) y se abre una fila nueva. Registra `ROL_ASIGNADO`.
- Nuevo `DELETE /usuarios/{id}/roles/{rol}` (sólo `ADMIN`): revocación lógica (`revocada_en = now()`, la fila no se borra) preservando el historial. `200`; `404` si el usuario no existe o no tiene ese rol vigente; `409` por autoprotección RN-05 (revocar el propio `ADMIN`, o dejar el sistema sin ningún `ADMIN` vigente). Registra `ROL_REVOCADO`.
- Nuevo `GET /eventos` (sólo `ADMIN`): auditoría paginada de `evento_seguridad` con filtros por rango de fechas (`desde`, `hasta`) y por `actor` (coincidencia exacta), ordenada por `cuando` descendente. `200`; `422` si la paginación o el rango son inválidos.
- Los cinco endpoints se montan en el grupo protegido (exigen sesión y no quedan exentos del bloqueo por contraseña pendiente) y declaran `Depends(require_roles("ADMIN"))`: un usuario autenticado sin `ADMIN` recibe `403 PERMISOS_INSUFICIENTES`.
- Sin cambios de esquema: `usuario`, `asignacion_rol` y `evento_seguridad` ya existen en `001_auth_core`. Sin cambios en las dependencias ni en los contratos de `/auth/*`.

## Capabilities

### New Capabilities

- `administracion-usuarios`: alta de personal por un administrador, consulta del historial de roles, asignación con vencimiento opcional, revocación lógica que preserva historial y las dos garantías de autoprotección de RN-05 (no revocar el propio `ADMIN`, no dejar el sistema sin administradores vigentes).
- `auditoria-eventos`: consulta paginada del registro de seguridad (`evento_seguridad`) restringida a `ADMIN`, con filtros por rango temporal y actor y orden estable por fecha descendente.

### Modified Capabilities

<!-- ninguna: los contratos de /auth/*, la autorización RBAC y el esquema de las tablas no cambian -->

## Impact

- **Código afectado**:
  - `app/modules/usuarios/router.py`: routers `router_admin_usuarios` (`/usuarios`) y `router_admin_eventos` (`/eventos`), más los handlers.
  - `app/modules/usuarios/schemas.py`: `SolicitudAltaUsuario`, `UsuarioCreado`, `AsignacionRolPublica`, `HistorialRoles`, `SolicitudAsignacionRol`, `RespuestaRevocacionRol`, `EventoPublico`.
  - `app/modules/usuarios/repository.py`: alta de usuario, listado de asignaciones, apertura/cierre de asignación, conteo de administradores vigentes y consulta paginada de eventos.
  - `app/modules/usuarios/service.py`: reglas de alta, asignación, revocación y autoprotección, y los tres eventos de auditoría nuevos.
  - `main.py`: montaje de los dos routers nuevos en `router_protegido`.
- **APIs**: cinco endpoints nuevos; ninguno existente cambia de código de respuesta ni de contrato.
- **Dependencias y datos**: depende de C-10 (`require_roles`) y reutiliza la auditoría de C-09/C-11 (`auditar_acceso`, `obtener_sesion_auditoria`). Sin migración: las tablas y sus restricciones ya existen. `C-13` refactorizará los accesos a datos sin cambiar estos contratos.
- **Fuera de alcance**: listado y baja de usuarios (`GET /usuarios`, `DELETE /usuarios/{id}`), activación/desactivación (`activo`), reset de contraseña por un tercero, alta de clientes/vehículos (C-15), la jerarquía de repositorios y el `UnitOfWork` (C-13/C-14), y el índice sobre `evento_seguridad` (diferido y documentado en `design.md`).
