# Proposal

## Why

No existe un endpoint público de auto-registro: un visitante no puede crear su cuenta, rol `CLIENTE` y ficha de cliente de forma atómica. El flujo de recepción (C-15) cubre el alta por personal, pero el auto-registro público (RN-02) requiere una única transacción que escriba `Usuario` + `AsignacionRol(CLIENTE)` + `Cliente`, con rollback total ante cualquier fallo, sin dejar huérfanos ni auditar eventos parciales.

## What Changes

- Nuevo endpoint público `POST /auth/registro` (201/409/422) en `router_publico` del módulo `usuarios`.
- Nuevo schema de entrada `SolicitudRegistro` (`email`, `nombre`, `password`, `documento`, `telefono`) con `extra="forbid"` y respuesta `UsuarioRegistrado` sin `password_hash`.
- Nuevo servicio `registrar_cliente` que calcula el hash de contraseña **antes** de abrir el `UnitOfWork`, crea las tres entidades en un único bloque atómico y registra `evento_seguridad` con acción `USUARIO_AUTO_REGISTRADO` dentro de la misma transacción.
- Detección de duplicados por email (`usuario.email` UNIQUE) y por documento (`cliente.documento` UNIQUE) traducida a `409` (`EMAIL_DUPLICADO` / `DOCUMENTO_DUPLICADO`) sin residuos.
- Reutilización de las restricciones únicas de base de datos para resolver la carrera concurrente (uno solo persiste).
- Sin migración Alembic: las tablas e índices ya existen desde C-06/C-07.

## Capabilities

### New Capabilities

- (ninguna)

### Modified Capabilities

- `autenticacion-sesion`: se agrega el requisito de auto-registro público atómico (contrato, escritura de las tres entidades en un solo `UnitOfWork`, hash previo a la transacción, `409` por email o documento duplicado sin residuos, `422` por contrato inválido, `201` sin `password_hash`, evento `USUARIO_AUTO_REGISTRADO` y rollback total ante fallo).

## Impact

- Código afectado: `app/modules/usuarios/schemas.py`, `app/modules/usuarios/service.py`, `app/modules/usuarios/router.py`, y un nuevo `UnitOfWork` de registro que compone repositorios de `usuarios` y `clientes`.
- APIs: nuevo endpoint `POST /auth/registro` bajo `router_publico` (ya montado en `main.py`).
- Dependencias: C-09 (auth-login-jwt), C-14 (unit-of-work), C-15 (clientes-vehiculos).
- Tests: `tests/test_registro_atomico.py` con los escenarios de éxito, rollback, duplicados y concurrencia.
- Sin cambios de schema/migración.