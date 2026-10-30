# Proposal

## Why

Los modelos de identidad ya existen (`usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`, C-06) y el hashing asincrónico está listo (C-03), pero la API todavía no puede emitir ni validar una sesión: no hay `POST /auth/login`, no hay cookie de sesión y no hay dependencia que resuelva "quién llama". Sin esto no se puede cumplir RN-04 (roles vigentes en base por petición), RN-07 (invalidación de sesiones al cambiar contraseña), RN-08 (límite de intentos) ni RN-09 (login opaco), y todos los endpoints de dominio de los capítulos 5 y 6 quedan inalcanzables.

## What Changes

- **Nuevo** módulo de sesión dentro de `app/modules/usuarios/`: `POST /auth/login`, `POST /auth/logout`, `GET /auth/yo`.
- **Nuevo** emisor/validador de JWT HS256 firmado con `jwt_secret` de `pydantic-settings`; claims `sub`, `iat`, `exp` y `roles` (informativos, RN-04), entregado en cookie `access_token` con `HttpOnly`, `SameSite=Lax`, `max_age` = `access_token_ttl_min` y `secure` derivado de `entorno`.
- **Nuevo** límite de intentos RN-08: conteo de `intento_acceso` fallidos por `(email, ip)` en la ventana de `login_ventana_seg`; al alcanzar `login_max_intentos` responde `429` con `Retry-After` **sin** ejecutar bcrypt. El estado vive en PostgreSQL, nunca en memoria del proceso ni en Redis.
- **Nuevo** registro de auditoría de acceso: fila en `intento_acceso` y fila en `evento_seguridad` (`LOGIN_OK`, `LOGIN_FALLIDO`, `LOGIN_BLOQUEADO`, `LOGOUT`) escritas en una **sesión/transacción independiente** que commitea aunque el login falle (KB 09 §5). Es la única excepción documentada a la regla dura #2 y queda justificada en `design.md`.
- **Nuevo** dependency `obtener_usuario_actual` en `app/core/dependencies.py`: valida cookie, firma HS256, `exp`, usuario `activo` y compara `iat` con `password_cambiada_en` con precisión de microsegundos (RN-07).
- **Nuevo** lectura de roles vigentes desde `asignacion_rol` (`revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`) para `GET /auth/yo`; los `roles` del token se ignoran para decidir (RN-04). La autorización por rol sigue fuera de alcance (C-10).
- **Sin migración**: el esquema de C-06 ya cubre todo (índice `ix_intento_acceso_email_ip_cuando`, columnas de `usuario`, `asignacion_rol`, `evento_seguridad`). No se agregan tablas, columnas ni índices.
- **Sin cambios de configuración**: `jwt_secret`, `access_token_ttl_min`, `login_max_intentos`, `login_ventana_seg` y `entorno` ya existen en `.env.example`.

**BREAKING**: ninguna. Los endpoints son nuevos y no se modifica ningún contrato existente.

## Capabilities

### New Capabilities

- `autenticacion-sesion`: emisión, transporte en cookie y validación de sesiones autenticadas con JWT, control de intentos de login (RN-08) y auditoría de acceso en `intento_acceso` / `evento_seguridad`.

### Modified Capabilities

- Ninguna. `http-contracts` (formato de error y `Retry-After`), `criptografia-asincrona` (`verify_password_o_dummy`), `persistencia-base` (sesión sin commit) y `modelos-autenticacion` (tablas e índices) se consumen tal como están especificadas. Los roles del token son informativos por diseño (RN-04), no un cambio de la especificación de modelos.

## Impact

- **Código afectado**
  - Nuevos: `app/modules/usuarios/schemas.py`, `app/modules/usuarios/repository.py`, `app/modules/usuarios/service.py`, `app/modules/usuarios/router.py`, `app/core/dependencies.py`.
  - Modificados: `app/core/seguridad.py` (helpers de JWT y armado de la cookie), `main.py` (montaje del router `/auth`), `tests/conftest.py` (fixture que cubre la sesión independiente de auditoría).
  - Sin cambios: modelos de `app/modules/usuarios/models.py`, migraciones, `seed.py`, `CHANGES.md`.
- **APIs**: se agregan `POST /auth/login` (`200`, `401`, `422`, `429`), `POST /auth/logout` (`200`) y `GET /auth/yo` (`200`, `401`). No se modifica ningún endpoint existente.
- **Dependencias**: ninguna nueva; `PyJWT==2.8.0` ya está en `requirements.txt`.
- **Base de datos**: sólo escrituras de datos (`intento_acceso`, `evento_seguridad`), sin DDL.
- **Fuera de alcance explícito**: autorización por rol y grupos de rutas (C-10), cambio de contraseña (C-11), alta de personal (C-12), repositorios genéricos y Unit of Work (C-13/C-14), auto-registro (C-17), archivos `.http` de integración (C-20).
