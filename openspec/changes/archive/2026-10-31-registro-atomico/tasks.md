# Tasks

## 1. Safety-net baseline

- [x] 1.1 Ejecutar la suite completa actual (`pytest -q`) y registrar verde como baseline.

## 2. Schemas (TDD)

- [x] 2.1 RED: test de contrato inválido (`tests/test_registro_atomico.py`) → `422 ERROR_VALIDACION` por campo extra, contraseña corta o sin complejidad.
- [x] 2.2 GREEN: implementar `SolicitudRegistro` y `UsuarioRegistrado` en `app/modules/usuarios/schemas.py` con `extra="forbid"`, validadores de email/contraseña/nombre/documento/teléfono; verificar que 2.1 pasa.

## 3. Unit of Work (TDD)

- [x] 3.1 GREEN: implementar `RegistroUnitOfWork` en `app/modules/usuarios/unit_of_work.py` componiendo `UsuarioRepository`, `AsignacionRolRepository`, `EventoSeguridadRepository` y `ClienteRepository`; verificar importación e instanciación con una sesión.

## 4. Servicio (TDD)

- [x] 4.1 RED: test de alta exitosa `201` sin `password_hash` y persistencia de las 3 entidades.
- [x] 4.2 GREEN: implementar `registrar_cliente` en `app/modules/usuarios/service.py` (hash antes del bloque, creación atómica de `Usuario` + `AsignacionRol(CLIENTE)` + `Cliente`, evento `USUARIO_AUTO_REGISTRADO`); verificar que 4.1 pasa.
- [x] 4.3 RED: test de fallo al crear el cliente → rollback total (0 filas en las 3 tablas).
- [x] 4.4 GREEN: asegurar que toda excepción dentro del bloque revierte; verificar que 4.3 pasa.
- [x] 4.5 RED: test de email duplicado → `409 EMAIL_DUPLICADO` sin residuos.
- [x] 4.6 GREEN: pre-chequeo + captura de `IntegrityError` en el flush del usuario; verificar que 4.5 pasa.
- [x] 4.7 RED: test de documento duplicado → `409 DOCUMENTO_DUPLICADO` sin residuos.
- [x] 4.8 GREEN: pre-chequeo + captura de `IntegrityError` en el flush del cliente; verificar que 4.7 pasa.
- [x] 4.9 RED: test de login inmediato tras registro exitoso.
- [x] 4.10 GREEN: asegurar `activo=True`, `debe_cambiar_password=False` y hash verificable; verificar que 4.9 pasa.

## 5. Router (TDD)

- [x] 5.1 RED: test del endpoint público `POST /auth/registro` (`201`/`409`/`422`) sin cookie.
- [x] 5.2 GREEN: agregar el handler en `router_publico` de `app/modules/usuarios/router.py` con `get_session` y `RegistroUnitOfWork`; verificar que 5.1 pasa.
- [x] 5.3 RED: test de dos registros concurrentes con el mismo email → uno solo persiste.
- [x] 5.4 VERIFY: el test de concurrencia pasa sobre PostgreSQL real; verificar conteos finales.

## 6. Refactor-verification

- [x] 6.1 Ejecutar la suite completa; contratos HTTP sin cambios.
- [x] 6.2 `alembic check` limpio.
- [x] 6.3 Agregar `test/registro.http` con casos felices y de error; verificar que el archivo existe y es válido.

## Workflow follow-up

- Archivar el change tras la revisión y marcar `[x]` en `CHANGES.md`.