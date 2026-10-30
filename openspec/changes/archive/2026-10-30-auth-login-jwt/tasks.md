# Tasks

> Ciclo TDD estricto en cada unidad de comportamiento: **Rojo** (test que falla) → **Verde** (implementación mínima) → **Triangular** (segundo/tercer caso que obliga a generalizar) → **Refactor** (sin cambiar comportamiento; la suite sigue verde). Ningún task de implementación sin su test previo.

## 1. Safety net y preparación

- [x] 1.1 Correr la suite completa (`pytest -q`) **antes de tocar código** y guardar la salida como línea base. Verificar: se conoce el estado inicial exacto (verde o con fallos/skips preexistentes) y no se confunde con regresiones propias.
- [x] 1.2 Confirmar el estado de partida: `openspec list --json` sin changes activos, `app/core/configuracion.py` con `jwt_secret`, `access_token_ttl_min`, `login_max_intentos`, `login_ventana_seg` y `entorno`, y `app/core/seguridad.py` con `verify_password_o_dummy`. Verificar: si falta alguno, detenerse y escalar (no agregar configuración ni firmas silenciosamente).
- [x] 1.3 Verificar que **no** hace falta migración: correr `alembic check` (o un `--autogenerate` en seco que se descarta) y confirmar que no hay diferencias entre modelos y esquema. Verificar: no se crea ni modifica nada en `migrations/versions/`.

## 2. Emisión de token (`app/core/seguridad.py`)

- [x] 2.1 **Rojo**: crear `tests/test_auth_token.py` con un test que emita un token para un usuario y espere `sub`, `iat`, `exp` y `roles`. Verificar: falla con `ImportError`/`AttributeError` porque `crear_token_acceso` no existe.
- [x] 2.2 **Verde**: implementar `crear_token_acceso(usuario_id: int, roles: list[str], iat: datetime) -> str` con `jwt.encode(..., algorithm="HS256")` y `exp = iat + access_token_ttl_min`. Verificar: el test de 2.1 pasa.
- [x] 2.3 **Triangular**: agregar tests de `exp` exacto (`iat + TTL`) y de `roles` como lista de strings. Verificar: ambos pasan y obligan a no hardcodear los claims.
- [x] 2.4 **Triangular (RN-07)**: test que serializa un `iat` con microsegundos y, tras decodificar, lo recupera como `datetime` con los mismos microsegundos. Verificar: pasa usando `iat` como string ISO-8601 (D6); falla si se usa un entero.
- [x] 2.5 **Rojo**: tests de rechazo de `decodificar_token_acceso`: firma inválida, token expirado, `alg=none`/`HS512` y token sin `iat`. Verificar: todos fallan porque la función no existe.
- [x] 2.6 **Verde**: implementar `decodificar_token_acceso(token: str) -> dict[str, Any]` con `algorithms=["HS256"]`, `options={"require": ["exp", "iat", "sub"]}` y `leeway=0`. Verificar: los tests de 2.5 pasan y ninguno acepta un token de otro algoritmo.
- [x] 2.7 **Refactor**: extraer el parseo de `iat` (string ISO-8601 / entero defensivo) a un helper privado con type hints y docstring. Verificar: `pytest tests/test_auth_token.py -q` sigue verde.

## 3. Cookie de sesión

- [x] 3.1 **Rojo**: test de `construir_cookie_sesion(...)` sobre `entorno="dev"` esperando `access_token` con `httponly=True`, `samesite="lax"`, `path="/"`, `max_age = ttl*60` y `secure=False`. Verificar: falla porque la función no existe.
- [x] 3.2 **Verde**: implementar `construir_cookie_sesion(respuesta, token, configuracion)` con `response.set_cookie(...)` según D7. Verificar: el test de 3.1 pasa.
- [x] 3.3 **Triangular**: test con `entorno="produccion"` → `secure=True`, y con `entorno="test"` → `secure=False`. Verificar: ambos pasan sin duplicar la lógica de armado.
- [x] 3.4 **Triangular**: test del borrado de cookie (`construir_cookie_borrado`) con los mismos `path`, `httponly`, `samesite` y `secure`, y `max_age=0`. Verificar: pasa y los atributos coinciden con los del set (si difieren, el navegador conserva la cookie).
- [x] 3.5 **Refactor**: unificar la derivación de `secure` en un único helper. Verificar: la suite de cookie sigue verde.

## 4. Auditoría en transacción independiente

- [x] 4.1 Agregar en `tests/conftest.py` la fixture `contexto_auth` que overridea **`get_session` y `obtener_sesion_auditoria`** con fábricas ligadas a la misma conexión externa (`join_transaction_mode="create_savepoint"`). Verificar: una prueba mínima que use la fixture ve sus propias escrituras y la base queda limpia al terminar el test.
- [x] 4.2 **Rojo**: test que llama a `auditar_acceso(...)` esperando una fila en `intento_acceso` y otra en `evento_seguridad`, visibles desde la sesión de test. Verificar: falla porque `obtener_sesion_auditoria` y `auditar_acceso` no existen.
- [x] 4.3 **Verde**: implementar `obtener_sesion_auditoria()` en `app/modules/usuarios/repository.py` (o `service.py`, según D3), `registrar_intento`/`registrar_evento` y el helper `auditar_acceso` que abre su sesión, hace `async with sesion.begin()` y commitea. Verificar: el test de 4.2 pasa.
- [x] 4.4 **Triangular (independencia)**: test que provoca el `rollback` de la sesión del request (excepción de dominio) y verifica que el intento y el evento **siguen** persistidos. Verificar: pasa; confirmar en el test que las sesiones usadas son objetos distintos.
- [x] 4.5 **Triangular (política)**: test que hace fallar la fábrica de sesión de auditoría y verifica que la excepción **se propaga** (no se responde `200` sin rastro). Verificar: pasa según D13; si se decide *best effort*, actualizar este test y el design.
- [x] 4.6 **Refactor**: aislar la escritura de auditoría detrás de una interfaz mínima (`Protocol` o dataclass `RegistroAcceso`) para que C-14 la reconozca como sub-UoW de auditoría. Verificar: suite de auditoría verde.

## 5. Login exitoso

- [x] 5.1 **Rojo**: `tests/test_auth_login.py::test_login_exitoso_setea_cookie_httponly` contra PostgreSQL real (usuario activo sembrado por el propio test). Verificar: falla con `404` porque el endpoint no existe.
- [x] 5.2 **Verde**: crear `schemas.py` (`SolicitudLogin` con `extra="forbid"`, `EmailStr`, `password` 1..72), `repository.py::buscar_usuario_por_email` con `selectinload(Usuario.asignaciones)`, `service.py::iniciar_sesion` mínimo y `router.py::login`; montar el router en `main.py`. Verificar: el test de 5.1 pasa (200 y `Set-Cookie` con los atributos esperados).
- [x] 5.3 **Triangular**: test del cuerpo de respuesta — `usuario.id`, `usuario.email`, `roles` vigentes, `token.iat`/`token.exp` presentes y **ningún** campo `password_hash`. Verificar: pasa con el schema `RespuestaSesion`.
- [x] 5.4 **Triangular (contrato)**: tests de `422` para campo extra, email inválido, contraseña vacía y contraseña de 73 caracteres; ninguno debe emitir cookie. Verificar: los cuatro pasan por el handler existente de `RequestValidationError`.
- [x] 5.5 **Triangular (RN-04)**: test de usuario con dos asignaciones, una vigente y otra revocada/vencida → el token y la respuesta incluyen sólo el rol vigente. Verificar: pasa filtrando por `revocada_en`/`vence_en` (D11).
- [x] 5.6 **Refactor**: separar en `service.py` la orquestación (`rate limit → verificación → emisión → auditoría`) de la construcción de la respuesta. Verificar: `pytest tests/test_auth_login.py -q` verde.
- [x] 5.7 **Docs**: documentar en `README.md` el flujo de login (nombre de la cookie, TTL, atributos y significado de `ENTORNO` para `Secure`) y verificar que las variables citadas coinciden con `.env.example`.

## 6. Login opaco (RN-09)

- [x] 6.1 **Rojo**: test de contraseña incorrecta → `401` con body uniforme y sin cookie. Verificar: falla porque hoy no existe la rama de error.
- [x] 6.2 **Verde**: usar `verify_password_o_dummy(..., app_state=request.app.state)` y lanzar `NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")` (regla dura #1). Verificar: el test de 6.1 pasa.
- [x] 6.3 **Triangular (enumeración)**: test que compara las respuestas de email inexistente vs. contraseña incorrecta y exige igualdad de `status_code`, `detail` y `codigo`, y ausencia de `Set-Cookie` en ambas. Verificar: pasa sin distinguir ramas en el handler.
- [x] 6.4 **Triangular (inactivo)**: test de usuario con `activo=false` y contraseña correcta → `401` idéntico a los anteriores. Verificar: pasa; la rama de inactivo ocurre **después** de verificar el hash (no antes).
- [x] 6.5 **Triangular (dummy)**: test con espía sobre la verificación que confirma que se ejecuta bcrypt igualmente cuando el usuario no existe. Verificar: pasa y demuestra que no hay atajo por email inexistente.
- [x] 6.6 **Refactor**: unificar los tres caminos en una sola función que devuelva `(usuario|None, ok)` antes de decidir la excepción. Verificar: los cuatro tests de opacidad siguen verdes.

## 7. Límite de intentos (RN-08)

- [x] 7.1 **Rojo**: test que registra los fallos máximos para un `(email, ip)` y espera `429` con `Retry-After` en la petición siguiente. Verificar: falla (hoy responde `401`).
- [x] 7.2 **Verde**: implementar `contar_intentos_fallidos(email, ip, desde)` en `repository.py` y el corte en `service.py` con `DemasiadasPeticionesError(reintentar_despues=...)` calculado según D5. Verificar: el test de 7.1 pasa y la cabecera existe.
- [x] 7.3 **Triangular (costo cero)**: test con espía sobre `verify_password_o_dummy` que verifica que **no se invoca** en la petición bloqueada. Verificar: pasa.
- [x] 7.4 **Triangular (umbral D4)**: test que fija la semántica — el intento que alcanza el límite responde `401`, y recién la petición siguiente responde `429`. Verificar: pasa y deja explícito el umbral acordado.
- [x] 7.5 **Triangular (ventana)**: test que envejece las filas de `intento_acceso` más allá de `login_ventana_seg` y confirma que el login vuelve a procesarse normal (no `429`), y que `Retry-After` está acotado entre 1 y la ventana. Verificar: pasa manipulando `cuando` directamente por SQL.
- [x] 7.6 **Triangular (no autoextensión)**: test que repite la petición bloqueada varias veces y verifica que el conteo de `intento_acceso` **no** crece y que sí se registran eventos `LOGIN_BLOQUEADO`. Verificar: pasa según D4.
- [x] 7.7 **Triangular (aislamiento)**: tests de que los fallos de otro email o de otra IP no bloquean a este `(email, ip)`. Verificar: ambos pasan.
- [x] 7.8 **Refactor**: extraer `calcular_retry_after(ultimos_fallos, ahora, ventana)` como función pura y testearla sin HTTP. Verificar: `pytest tests/test_auth_rate_limit.py -q` verde.

## 8. Resolución de la sesión (`obtener_usuario_actual`)

- [x] 8.1 **Rojo**: test de endpoint protegido sin cookie → `401` uniforme. Verificar: falla porque `app/core/dependencies.py` no existe.
- [x] 8.2 **Verde**: implementar `obtener_usuario_actual(request, sesion=Depends(get_session))` leyendo la cookie, decodificando y cargando el usuario con `selectinload(Usuario.asignaciones)`; cablearlo en `GET /auth/yo` como primer consumidor. Verificar: el test de 8.1 pasa.
- [x] 8.3 **Triangular**: tests de firma alterada y de `exp` en el pasado → `401` en ambos. Verificar: pasan sin exponer el motivo real en el body.
- [x] 8.4 **Triangular**: test de usuario desactivado con token válido → `401`. Verificar: pasa releyendo `activo` en la base, no del token.
- [x] 8.5 **Triangular**: happy path — token válido → `200` y la respuesta no incluye `password_hash`. Verificar: pasa.
- [x] 8.6 **Refactor**: devolver un `SesionActual` (usuario + `iat` + `exp`) en vez de una tupla, con type hints. Verificar: los cinco tests del grupo verdes.

## 9. Invalidación por cambio de contraseña (RN-07)

- [x] 9.1 **Rojo**: test con `password_cambiada_en = iat + 1s` → la petición responde `401`. Verificar: falla porque la comparación no existe.
- [x] 9.2 **Verde**: comparar en `obtener_usuario_actual` con `iat < password_cambiada_en` (ambos `timezone-aware`) y lanzar el `401` uniforme. Verificar: el test de 9.1 pasa.
- [x] 9.3 **Triangular (microsegundos)**: test con `iat` y `password_cambiada_en` en el mismo segundo y `password_cambiada_en = iat + 1 microsegundo` → `401`. Verificar: pasa; falla si se truncan a segundos.
- [x] 9.4 **Triangular**: `password_cambiada_en = NULL` → `200`, y token emitido después del cambio → `200`. Verificar: ambos pasan (no se invalida lo que nunca cambió).
- [x] 9.5 **Triangular**: token con `iat` no parseable → `401` sin `500`. Verificar: pasa.
- [x] 9.6 **Refactor**: extraer `token_anterior_al_cambio(iat, password_cambiada_en)` como función pura con tests unitarios propios. Verificar: la suite del grupo sigue verde.

## 10. Sesión actual (`GET /auth/yo`) y cierre de sesión

- [x] 10.1 **Rojo**: test de `GET /auth/yo` autenticado esperando `usuario`, `roles` vigentes e `iat`/`exp`. Verificar: falla porque el endpoint aún no devuelve el payload completo.
- [x] 10.2 **Verde**: implementar el handler con `RespuestaSesion` (misma forma que login, D15). Verificar: el test de 10.1 pasa.
- [x] 10.3 **Triangular (RN-04)**: tests de rol revocado y de `vence_en` en el pasado → no aparecen; y rol inyectado en el token que el usuario no tiene → tampoco aparece. Verificar: los tres pasan releyendo la base.
- [x] 10.4 **Rojo**: test de `POST /auth/logout` con cookie válida esperando `200` y una instrucción de borrado de `access_token`. Verificar: falla porque el endpoint no existe.
- [x] 10.5 **Verde**: implementar `logout` (D16) reutilizando `construir_cookie_borrado`. Verificar: el test de 10.4 pasa.
- [x] 10.6 **Triangular**: logout sin cookie → `200`; logout con token inválido → `200` y **sin** evento; logout con token válido → evento `LOGOUT` con el email como actor. Verificar: los tres pasan.
- [x] 10.7 **Refactor**: unificar la emisión y el borrado de cookie en un único módulo de respuesta. Verificar: `pytest tests/test_auth_sesion.py -q` verde.

## 11. Verificación integral

- [x] 11.1 Correr `pytest -q` completo y comparar con la línea base de 1.1. Verificar: 0 fallos nuevos, 0 warnings de sesión abierta y ningún test que escape de la transacción de prueba.
- [x] 11.2 Volver a correr `alembic check` y revisar `migrations/versions/`. Verificar: no hay migración nueva; si el apply necesitó una (índice/columna), el design debe actualizarse y la migración ser una tarea separada revisada a mano.
- [x] 11.3 Auditoría de reglas duras por búsqueda: sin `HTTPException` en `app/modules/usuarios/` ni `app/core/dependencies.py`; sin `commit()` en `router.py`/`service.py` fuera de `auditar_acceso`; todos los handlers `async def`; todos los schemas de entrada con `extra="forbid"`; sin `lazy` implícito. Verificar: los greps quedan vacíos y se registran en la revisión.
- [x] 11.4 Verificar la organización de artefactos: la suite nueva vive en `tests/` (`test_auth_token.py`, `test_auth_login.py`, `test_auth_rate_limit.py`, `test_auth_sesion.py`) y `test/` sigue conteniendo sólo `.http` y `seed.sql`. Verificar: `test/` sin archivos `.py`.
- [x] 11.5 Matriz de cobertura requisito→test: mapear cada uno de los 9 requisitos del delta `autenticacion-sesion` a al menos un test y anotar el nombre del test junto al requisito. Verificar: ningún escenario del delta queda sin test.

## Workflow follow-up

- Confirmar con un humano las 5 notas de governance de `design.md` (umbral del rate limit, bloqueo no registrado, propagación de fallos de auditoría, `secure` por entorno, IP sin `X-Forwarded-For`) antes de empezar el apply.
- Archivar el change con `/opsx:archive auth-login-jwt` después de la revisión.
- Durante el archive se sincroniza `autenticacion-sesion` a `openspec/specs/` y luego se marca `[C-09]` como `[x]` en `CHANGES.md`.
