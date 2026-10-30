# Proposal

## Why

El sistema necesita persistir la identidad de usuarios, sus asignaciones de rol, los intentos de acceso y los eventos de seguridad para soportar autenticación, autorización (RBAC) y auditoría. Sin estas tablas no se puede implementar login, registro ni control de acceso — son el cimiento de toda la capa de seguridad (capítulos 2–6 del TP).

## What Changes

- **Modelo `Usuario`**: tabla `usuario` con `email` UNIQUE, `password_hash`, `activo`, `debe_cambiar_password`, `password_cambiada_en` (timestamptz nullable). SQLModel con `table=True`.
- **Modelo `AsignacionRol`**: tabla `asignacion_rol` con `rol` CHECK (`ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`), `desde`, `vence_en`, `revocada_en`, `otorgada_por`. Índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` que garantiza RN-03.
- **Modelo `IntentoAcceso`**: tabla `intento_acceso` con `cuando`, `email`, `ip`, `exito`. Índice compuesto `(email, ip, cuando)` para consultas de rate-limiting (RN-08).
- **Modelo `EventoSeguridad`**: tabla `evento_seguridad` con `cuando`, `actor`, `accion`. Registro de auditoría general.
- **Relaciones**: `Usuario.asignaciones` ↔ `AsignacionRol.usuario` bidireccional con `back_populates` y `lazy="raise"`.
- **Migración Alembic `001_auth_core`**: revisada a mano, incluye el índice único parcial, el índice compuesto y los CHECKs.
- **Tests de integridad**: segundo rol abierto del mismo tipo → `IntegrityError`; email duplicado → `IntegrityError`; CHECK de rol inválido rechazado; downgrade exitoso.

## Capabilities

### New Capabilities
- `modelos-autenticacion`: Modelos SQLModel y migración Alembic para las tablas de identidad, roles y auditoría de acceso (`usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`).

### Modified Capabilities
_(ninguna — las tablas son nuevas y no modifican requisitos de specs existentes)_

## Impact

- **Archivos nuevos**:
  - `app/modules/usuarios/models.py` — modelos SQLModel de las 4 tablas
  - `migrations/versions/001_auth_core.py` — migración Alembic
  - `test/test_auth_models.py` — tests de integridad contra PostgreSQL real
- **Archivos modificados**:
  - `migrations/env.py` — importar los modelos para que Alembic detecte metadata
- **Dependencias**: requiere C-05 (`database-lifecycle`) completado (motor async, Alembic scaffolding)
- **APIs afectadas**: ninguna en este change — los endpoints de auth se construyen en changes posteriores (C-08, C-09)
