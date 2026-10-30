# Tasks

## 1. Modelos SQLModel

- [ ] 1.1 Crear `app/modules/usuarios/models.py` con modelo `Usuario` (tabla `usuario`): `id` PK, `email` UNIQUE, `nombre`, `password_hash`, `activo` default true, `debe_cambiar_password` default false, `password_cambiada_en` timestamptz nullable. Verificar: test de inserción exitosa y test de email duplicado → `IntegrityError`.
- [ ] 1.2 Agregar modelo `AsignacionRol` en el mismo archivo: `id` PK, `usuario_id` FK, `rol` con CHECK (ADMIN, RECEPCION, MECANICO, CLIENTE), `desde` timestamptz NOT NULL, `vence_en` nullable, `revocada_en` nullable, `otorgada_por` FK nullable. Constante `ROLES_VALIDOS`. `__table_args__` con `CheckConstraint` y `Index("uq_asignacion_rol_abierta", ..., unique=True, postgresql_where=...)`. Relación bidireccional `usuario ↔ asignaciones` con `lazy="raise"`. Verificar: test de rol inválido → CHECK error; test de segundo rol abierto del mismo tipo → `IntegrityError`; test de reasignación tras revocación → éxito.
- [ ] 1.3 Agregar modelo `IntentoAcceso` en el mismo archivo: `id` PK, `cuando` timestamptz NOT NULL, `email` NOT NULL, `ip` NOT NULL, `exito` bool NOT NULL. `__table_args__` con `Index("ix_intento_acceso_email_ip_cuando", ...)`. Verificar: test de inserción exitosa con timestamp, email e IP.
- [ ] 1.4 Agregar modelo `EventoSeguridad` en el mismo archivo: `id` PK, `cuando` timestamptz NOT NULL con server_default `func.now()`, `actor` NOT NULL, `accion` NOT NULL. Verificar: test de inserción con `cuando` automático.
- [ ] 1.5 Crear `app/modules/usuarios/__init__.py` vacío para convertir en paquete Python. Verificar: `import app.modules.usuarios.models` no lanza error.

## 2. Migración Alembic

- [ ] 2.1 Importar los modelos en `migrations/env.py` para que Alembic detecte el metadata de SQLModel. Verificar: `alembic check` no muestra errores de importación.
- [ ] 2.2 Generar migración con `alembic revision --autogenerate -m "001_auth_core"` y revisar/editar a mano: verificar que incluya el CHECK de rol, el índice único parcial `uq_asignacion_rol_abierta` y el índice compuesto `ix_intento_acceso_email_ip_cuando`. Verificar: la migración tiene los 3 elementos en `upgrade()` y los elimina en `downgrade()`.

## 3. Tests de integridad contra PostgreSQL

- [ ] 3.1 Crear `test/test_auth_models.py` con test de inserción exitosa de `Usuario` y test de email duplicado → `IntegrityError`. Tests requieren PostgreSQL real (`pytest.skip` si no hay conexión). Verificar: ambos tests pasan.
- [ ] 3.2 Agregar tests de `AsignacionRol`: rol inválido rechazado por CHECK; segundo rol abierto del mismo tipo → `IntegrityError` (RN-03); reasignación tras revocación exitosa. Verificar: los 3 tests pasan.
- [ ] 3.3 Agregar test de `lazy="raise"`: cargar `Usuario` sin `selectinload` y acceder a `asignaciones` → `InvalidRequestError`. Verificar: test pasa.
- [ ] 3.4 Agregar tests de `IntentoAcceso` (inserción exitosa) y `EventoSeguridad` (timestamp automático). Verificar: ambos tests pasan.
- [ ] 3.5 Agregar tests de migración: `alembic upgrade head` crea las 4 tablas; `alembic downgrade base` las elimina. Verificar: ambos tests pasan.

## 4. Verificación integral

- [ ] 4.1 Ejecutar `pytest test/test_auth_models.py -v` y confirmar que TODOS los tests pasan (o skip por falta de PostgreSQL). Ejecutar `pytest` completo y confirmar que no se rompió nada existente (los 3 fallos pre-existentes no cuentan). Verificar: 0 nuevos fallos.

## Workflow follow-up

- Archivar el change con `/opsx:archive auth-models` después de revisar la implementación.
- El spec `modelos-autenticacion` se sincroniza a `openspec/specs/` durante el archive.
