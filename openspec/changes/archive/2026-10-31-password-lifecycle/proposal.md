# Proposal

## Why

C-09 dejó implementada la comparación RN-07 (`iat` contra `password_cambiada_en`), pero ningún flujo escribe ese timestamp; C-10 bloquea con `403` a quien tiene `debe_cambiar_password=true`, pero no existe forma de levantar la bandera. Sin C-11, un usuario con contraseña provisoria queda en un callejón sin salida y las sesiones anteriores nunca se invalidan de verdad.

## What Changes

- Nuevo `POST /auth/cambiar-password`, montado en el grupo protegido de `/auth` (exige sesión y queda exento del gate RN-06 por prefijo).
- Nuevo schema `SolicitudCambioPassword` con `password_actual` y `password_nueva`, `extra="forbid"`, longitud 8–72 y complejidad mínima (al menos una mayúscula, una minúscula y un dígito); la nueva debe diferir de la actual. Todo incumplimiento responde `422`.
- Verificación de la contraseña actual con `verify_password_async` (bcrypt en `to_thread` acotado por el semáforo del `lifespan`); si falla, `401` uniforme `CREDENCIALES_INVALIDAS`, sin revelar la existencia del usuario ni dejar cambios persistidos.
- Hash de la contraseña nueva con `hash_password(..., app_state)`, nunca `hash_password_sync`.
- Persistencia atómica de `password_hash`, `password_cambiada_en = now()` con microsegundos (sin truncar) y `debe_cambiar_password = False` (RN-07).
- Respuesta `200` con `{"detail": "Contraseña actualizada"}`. **No** se reemite cookie: por RN-07 el token usado queda inválido y el cliente debe volver a autenticarse.
- Auditoría del evento `PASSWORD_CAMBIADA` en `evento_seguridad` con el email del usuario como actor, en la sesión independiente que ya usa `auditar_acceso`.
- Endurecer el handler global de `RequestValidationError` en `main.py` para que el `422` devuelva `loc`/`msg`/`type` sin `input`/`ctx`, evitando que las contraseñas enviadas se repitan en la respuesta; se agrega un test de regresión para login y cambio de contraseña.
- Invariante de organización de artefactos: `test/` contiene únicamente archivos `.http` y un único `.sql` (`seed.sql`); toda la suite pytest (`conftest.py`, `test_*.py`) vive en `tests/`. Se agrega un test guardián que falla si se rompe.

**BREAKING**: ninguna ruta ni código HTTP cambia. Único cambio transversal: el cuerpo del `422` deja de incluir `input`/`ctx` (endurecimiento de seguridad); los clientes que leían esos campos deben dejar de hacerlo.

## Capabilities

### New Capabilities

<!-- Ninguna: el comportamiento encaja en la capability de autenticación existente. -->

- Ninguna.

### Modified Capabilities

- `autenticacion-sesion`: se agrega el requisito de cambio de contraseña autenticado (contrato, verificación, persistencia, `401`/`422` e invalidación efectiva de sesiones previas) y se amplía el requisito de auditoría para incluir `PASSWORD_CAMBIADA`.

## Impact

- `app/modules/usuarios/schemas.py`: `SolicitudCambioPassword` y `RespuestaCambioPassword`.
- `app/modules/usuarios/repository.py`: `actualizar_password(...)` y la dependency de sesión dedicada al cambio.
- `app/modules/usuarios/service.py`: orquestación verificar → hashear → persistir → auditar.
- `app/modules/usuarios/router.py`: handler `POST /auth/cambiar-password`.
- `main.py`: el handler de `RequestValidationError` deja de exponer `input`/`ctx` (posible fuga de contraseñas en el `422`); el wiring de routers no cambia.
- `tests/test_auth_cambio_password.py`: suite del endpoint, del schema y de RN-07.
- `tests/test_estructura_artefactos.py`: guardián de `test/` vs `tests/`.
- `tests/conftest.py`: override de la nueva dependency de sesión en `contexto_auth`.
- `test/auth.http`: casos manuales del endpoint (solo `.http`).
- Sin migración: `password_hash`, `password_cambiada_en` y `debe_cambiar_password` ya existen en `001_auth_core`.
- Depende de C-09 y C-10 (ambos archivados). No modifica C-12 ni adelanta la jerarquía de C-13/C-14.
