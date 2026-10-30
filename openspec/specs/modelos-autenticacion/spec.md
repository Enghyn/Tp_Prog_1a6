# modelos-autenticacion Specification

## Purpose
Define los modelos de datos persistentes y la migración de base de datos para identidad de usuarios, asignación de roles (RBAC), registro de intentos de acceso y eventos de seguridad del taller mecánico.

## Requirements

### Requirement: Tabla usuario con email único
El sistema SHALL persistir usuarios en la tabla `usuario` con columnas `id` (PK autoincremental), `email` (VARCHAR UNIQUE NOT NULL), `nombre` (VARCHAR NOT NULL), `password_hash` (VARCHAR NOT NULL), `activo` (BOOLEAN NOT NULL DEFAULT true), `debe_cambiar_password` (BOOLEAN NOT NULL DEFAULT false) y `password_cambiada_en` (TIMESTAMPTZ nullable).

#### Scenario: Inserción exitosa de usuario
- **WHEN** se inserta un registro en `usuario` con email único y todos los campos requeridos
- **THEN** el registro se persiste correctamente con `activo=true` y `debe_cambiar_password=false` por defecto

#### Scenario: Email duplicado rechazado
- **WHEN** se intenta insertar un usuario con un email que ya existe en la tabla
- **THEN** la base de datos lanza `IntegrityError` por violación de la constraint UNIQUE sobre `email`

#### Scenario: password_cambiada_en nullable
- **WHEN** se inserta un usuario sin especificar `password_cambiada_en`
- **THEN** el campo queda en NULL indicando que la contraseña nunca fue cambiada

### Requirement: Tabla asignacion_rol con índice único parcial
El sistema SHALL persistir asignaciones de rol en la tabla `asignacion_rol` con CHECK constraint sobre `rol` (valores: ADMIN, RECEPCION, MECANICO, CLIENTE) y un índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` que garantiza RN-03.

#### Scenario: Asignación de rol válida
- **WHEN** se inserta una asignación con `rol` válido (ADMIN, RECEPCION, MECANICO o CLIENTE) y `usuario_id` existente
- **THEN** el registro se persiste con `desde` NOT NULL y `vence_en`, `revocada_en`, `otorgada_por` nullable

#### Scenario: Rol inválido rechazado por CHECK
- **WHEN** se intenta insertar una asignación con un valor de `rol` fuera del CHECK (ej. "GERENTE")
- **THEN** la base de datos rechaza la operación con error de CHECK constraint

#### Scenario: Segundo rol abierto del mismo tipo rechazado (RN-03)
- **WHEN** un usuario ya tiene una asignación abierta (revocada_en IS NULL) para rol X y se intenta insertar otra asignación abierta para el mismo rol X
- **THEN** la base de datos lanza `IntegrityError` por violación del índice único parcial

#### Scenario: Reasignación tras revocación permitida
- **WHEN** la asignación anterior para rol X fue revocada (revocada_en IS NOT NULL) y se inserta una nueva asignación abierta para el mismo rol X
- **THEN** la inserción se completa exitosamente porque el índice parcial solo considera filas con `revocada_en IS NULL`

### Requirement: Tabla intento_acceso con índice compuesto
El sistema SHALL registrar intentos de login en la tabla `intento_acceso` con columnas `id` (PK), `cuando` (TIMESTAMPTZ NOT NULL), `email` (VARCHAR NOT NULL), `ip` (VARCHAR NOT NULL), `exito` (BOOLEAN NOT NULL) e índice compuesto `(email, ip, cuando)` para consultas eficientes de rate-limiting.

#### Scenario: Registro de intento exitoso
- **WHEN** se inserta un registro de intento con `exito=true`
- **THEN** el registro se persiste con timestamp, email e IP del cliente

#### Scenario: Consulta de intentos por email e IP eficiente
- **WHEN** se consultan intentos fallidos para un email e IP en los últimos 60 segundos
- **THEN** la consulta utiliza el índice compuesto `(email, ip, cuando)` sin full table scan

### Requirement: Tabla evento_seguridad para auditoría
El sistema SHALL registrar eventos de auditoría de seguridad en la tabla `evento_seguridad` con columnas `id` (PK), `cuando` (TIMESTAMPTZ NOT NULL DEFAULT now()), `actor` (VARCHAR NOT NULL) y `accion` (VARCHAR NOT NULL).

#### Scenario: Registro de evento de seguridad
- **WHEN** se inserta un evento con actor "SISTEMA" y acción "seed_inicial"
- **THEN** el registro se persiste con el timestamp actual si no se especifica `cuando`

### Requirement: Relaciones bidireccionales con lazy raise
El modelo `Usuario` SHALL declarar relación `asignaciones` hacia `AsignacionRol` y `AsignacionRol` SHALL declarar relación `usuario` hacia `Usuario`, ambas con `back_populates` y `lazy="raise"` para forzar carga explícita con `selectinload`.

#### Scenario: Acceso lazy a relación lanza error
- **WHEN** se carga un `Usuario` sin `selectinload` y se intenta acceder a `usuario.asignaciones`
- **THEN** SQLAlchemy lanza `InvalidRequestError` por lazy="raise"

#### Scenario: Carga explícita con selectinload exitosa
- **WHEN** se carga un `Usuario` con `selectinload(Usuario.asignaciones)`
- **THEN** las asignaciones se cargan correctamente sin N+1 queries

### Requirement: Migración Alembic 001_auth_core reversible
El sistema SHALL proveer una migración Alembic `001_auth_core` que crea las 4 tablas con todas sus constraints, índices y relaciones, y que MUST ser reversible con `downgrade` limpio.

#### Scenario: Upgrade crea las tablas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** las tablas `usuario`, `asignacion_rol`, `intento_acceso` y `evento_seguridad` existen con todas las constraints e índices declarados

#### Scenario: Downgrade elimina las tablas
- **WHEN** se ejecuta `alembic downgrade base` tras el upgrade
- **THEN** las 4 tablas se eliminan completamente sin dejar artefactos en la base de datos
