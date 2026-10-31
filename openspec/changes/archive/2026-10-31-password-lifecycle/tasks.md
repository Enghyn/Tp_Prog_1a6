# Tasks

> Ciclo TDD estricto en cada unidad de comportamiento: **Rojo** (test que falla) → **Verde** (implementación mínima) → **Triangular** (casos que obligan a generalizar) → **Refactor** (sin cambiar comportamiento; la suite sigue verde). Ningún task de implementación sin su test previo. La secuencia es **unit-first**: los tests de schema, repositorio y service se ponen verdes antes de escribir el handler HTTP; los tests HTTP llegan recién en el grupo 5, cuando el endpoint ya existe. La evidencia del ciclo se registra en el resumen del apply.

## 1. Safety net y preparación

- [x] 1.1 Correr la suite completa (`pytest -q`) **antes de tocar código** y guardar la salida como línea base. Verificar: se conoce el número exacto de tests verdes, fallos y skips preexistentes (los tests de base se saltan si no hay PostgreSQL), y no se confunde una regresión propia con un fallo previo.
- [x] 1.2 Confirmar el estado de partida con lectura de solo lectura: `app/modules/usuarios/models.py` tiene `password_hash`, `password_cambiada_en` y `debe_cambiar_password`; `app/core/seguridad.py` expone `hash_password` y `verify_password_async`; `app/core/dependencies.py` expone `obtener_usuario_actual` y `token_anterior_al_cambio`; `router_autenticado` está montado en `router_protegido`; `main.py` responde a `RequestValidationError` con `exc.errors()`. Verificar: si falta cualquiera de esas piezas, detenerse y escalar; no se agrega configuración ni firmas en silencio.
- [x] 1.3 Verificar que **no** hace falta migración: correr `alembic check` (o un `--autogenerate` en seco que se descarta) y confirmar que no hay diferencias entre modelos y esquema. Verificar: `migrations/versions/` no recibe archivos nuevos.
- [x] 1.4 Confirmar el aislamiento de tests: `tests/conftest.py::contexto_auth` overridea `get_session` y `obtener_sesion_auditoria` con `join_transaction_mode="create_savepoint"`. Verificar: un test trivial que escribe y lee en la base ve sus datos y, al terminar, la base queda limpia.
- [x] 1.5 Documentar la línea base de seguridad del `422`: enviar un login con `password` inválido (por ejemplo, 73 caracteres) y guardar la respuesta actual. Verificar: se confirma si el cuerpo repite el valor enviado en `input`; eso justifica el task 5.4 y no se descubre recién al final.

## 2. Esquema de entrada (`SolicitudCambioPassword`)

- [x] 2.1 **Rojo**: crear `tests/test_auth_cambio_password.py` con tests **directos de Pydantic** (sin HTTP) que construyan `SolicitudCambioPassword` y esperen `ValidationError` para: falta `password_actual`, falta `password_nueva`, campo extra, `password_nueva` de 7 y de 73 caracteres, sin mayúscula, sin minúscula, sin dígito y `password_nueva == password_actual`. Verificar: fallan con `ImportError` porque el schema no existe.
- [x] 2.2 **Verde**: crear `SolicitudCambioPassword` en `app/modules/usuarios/schemas.py` con `ConfigDict(extra="forbid")`, `password_actual` 1–72, `password_nueva` 8–72, un `field_validator` de composición (mayúscula ASCII, minúscula ASCII, dígito) y un `model_validator(mode="after")` que rechaza la nueva igual a la actual. Verificar: los tests de 2.1 pasan.
- [x] 2.3 **Triangular (bordes y no normalización)**: tests de `password_nueva` de 8 y de 72 caracteres válidos → no lanzan; `password_actual` con espacios conserva el string exacto (el schema **no** aplica `strip`); `password_nueva` con espacios internos y los tres tipos de carácter → válida. Verificar: los tres pasan y fallan si se agrega una normalización indebida.
- [x] 2.4 **Refactor**: extraer la composición a un helper puro `validar_complejidad_password(...)` en `schemas.py` (no en `seguridad.py`, para no tocar el módulo criptográfico) y testearlo aparte. Verificar: `pytest tests/test_auth_cambio_password.py -q` sigue verde.

## 3. Repositorio y sesión dedicada (PostgreSQL real)

- [x] 3.1 **Rojo**: tests unitarios de `actualizar_password(sesion, usuario_id, password_hash, cambiada_en)` contra PostgreSQL real: actualiza las tres columnas, devuelve/verifica `rowcount == 1`, persiste `cambiada_en` con microsegundos exactos y lanza `NoAutenticadoError` uniforme cuando el `usuario_id` no existe (`rowcount == 0`). Verificar: fallan porque la función no existe.
- [x] 3.2 **Verde**: agregar en `repository.py` `obtener_sesion_cambio_password(request)` (sesión nueva desde `request.app.state.session_maker`, con fallback al `session_maker` global) y `actualizar_password(...)` con un único `UPDATE ... WHERE id = :id` y verificación de `rowcount`. Verificar: los tests de 3.1 pasan.
- [x] 3.3 **Triangular (atomicidad y límites)**: test que abre `async with sesion.begin():`, llama a `actualizar_password` y luego fuerza una excepción, comprobando que la fila queda intacta; test que confirma que `actualizar_password` **no** cierra la sesión ni hace `commit()` explícito. Verificar: ambos pasan.
- [x] 3.4 **Refactor**: type hints, docstring de la dependency y búsqueda de `commit()` en `repository.py` vacía. Verificar: `pytest tests/test_auth_cambio_password.py -q` verde.

## 4. Servicio (`cambiar_password`)

- [x] 4.1 **Rojo**: tests unitarios del service contra PostgreSQL real: con `password_actual` incorrecta lanza `NoAutenticadoError` uniforme y **no** modifica la fila; con la correcta actualiza hash, timestamp y bandera, y llama a `auditar_acceso` una vez con `accion="PASSWORD_CAMBIADA"`. Verificar: fallan porque `cambiar_password` no existe.
- [x] 4.2 **Verde**: implementar `cambiar_password(...)` con el orden de D3: `verify_password_async` → `hash_password` → `ahora = datetime.now(timezone.utc)` → `async with sesion_cambio.begin(): actualizar_password(...)` → `auditar_acceso(...)` → respuesta. Verificar: los tests de 4.1 pasan.
- [x] 4.3 **Triangular (reloj y auditoría)**: con un reloj fijo (patch de `datetime` en el service o helper `_ahora()` inyectable) el test verifica que `password_cambiada_en` es exactamente el instante fijado, con microsegundos, y que `RegistroAcceso.cuando` coincide; test de que la IP recibida se propaga a `RegistroAcceso.ip`; test de que un fallo de `auditar_acceso` se propaga. Verificar: los tres pasan.
- [x] 4.4 **Triangular (usuario provisorio)**: test con `debe_cambiar_password=true` que confirma que el service no lo bloquea y deja la bandera en `false`. Verificar: pasa.
- [x] 4.5 **Refactor**: encapsular el `401` uniforme en un helper compartido con el login, dejar `TODO(C-14)` junto al bloque `begin()` y verificar que no hay `commit()` en `service.py`. Verificar: `pytest tests/test_auth_cambio_password.py -q` verde.

## 5. Endpoint HTTP

- [x] 5.1 **Rojo**: tests HTTP con `contexto_auth`: cambio exitoso → `200` con `{"detail": "Contraseña actualizada"}`; `password_actual` incorrecta → `401` uniforme; sin cookie → `401`; `password_nueva` inválida o campo extra → `422`; usuario con `debe_cambiar_password=true` → `200`; respuesta sin `Set-Cookie` de `access_token` nuevo. Verificar: fallan con `404`/`405` porque el handler no existe.
- [x] 5.2 **Verde**: crear `RespuestaCambioPassword`, el handler `POST /auth/cambiar-password` en `router_autenticado` (con `request` para la IP) y montarlo. Verificar: los tests de 5.1 pasan.
- [x] 5.3 **Triangular (precedencia y contrato)**: test de que sin cookie el `401` gana aunque el body sea inválido; test de que un `422` por contraseña corta no incluye `password_actual` ni `password_nueva` en el cuerpo; test de que el `422` conserva `loc`, `msg` y `type`. Verificar: los tres pasan (el de fuga queda rojo hasta 5.4).
- [x] 5.4 **Verde (seguridad del `422`)**: endurecer el handler de `RequestValidationError` en `main.py` para devolver solo `loc`/`msg`/`type` (sin `input` ni `ctx`). Verificar: el test de fuga de 5.3 pasa y se agrega un test de regresión equivalente para `POST /auth/login`.
- [x] 5.5 **Docs y artefacto manual**: documentar el endpoint en `README.md` (body, códigos, que el `200` no renueva la cookie y que hay que reautenticarse) y crear `test/auth.http` con los casos feliz, `401`, `422` y cookie invalidada. Verificar: los ejemplos del README coinciden con el contrato del spec y `test/auth.http` es un archivo `.http` válido.

## 6. Integración con RN-07

- [x] 6.1 **Rojo**: test que hace login, cambia la contraseña con ese token y luego reutiliza el token viejo en `GET /auth/yo`, esperando `401`. Verificar: falla si `password_cambiada_en` no se persiste o se trunca.
- [x] 6.2 **Verde**: asegurar que el service captura `ahora` **después** del hash y antes del `UPDATE`, sin `replace(microsecond=0)`, y lo persiste tal cual. Verificar: el test de 6.1 pasa.
- [x] 6.3 **Triangular (token posterior y microsegundos)**: tras el cambio, login con la contraseña nueva y uso del token recién emitido en `GET /auth/yo` → `200`; con reloj fijo, `password_cambiada_en = iat + 1 microsegundo` → `401` y `iat == password_cambiada_en` → `200`. Verificar: los tres pasan sin redondeos.
- [x] 6.4 **Refactor**: reutilizar `token_anterior_al_cambio` sin duplicar la comparación en el service. Verificar: `pytest tests/test_auth_cambio_password.py tests/test_auth_rn07_integracion.py -q` verde.

## 7. Auditoría `PASSWORD_CAMBIADA`

- [x] 7.1 **Rojo**: test que, tras un cambio exitoso, consulta `evento_seguridad` y espera una fila con `accion="PASSWORD_CAMBIADA"`, `actor` igual al email del usuario, `ip` igual a la del request y `cuando` igual al instante persistido; y verifica que **no** se insertó una fila en `intento_acceso`. Verificar: falla porque no se audita.
- [x] 7.2 **Verde**: llamar a `auditar_acceso` con `exito=None` después del `UPDATE` confirmado, usando la sesión de auditoría existente. Verificar: el test de 7.1 pasa.
- [x] 7.3 **Triangular (fallo de auditoría)**: test que hace fallar la escritura de auditoría y confirma que la excepción se propaga (`500`) mientras la contraseña ya quedó cambiada en la base. Verificar: pasa y deja explícita la política de D6.
- [x] 7.4 **Refactor**: mantener `auditar_acceso` como único punto de escritura de `evento_seguridad`; no agregar SQL de auditoría en el módulo. Verificar: búsqueda de `insert(EventoSeguridad)` fuera de `repository.py` vacía.

## 8. Invariante de carpetas `test/` vs `tests/`

- [x] 8.1 **Caracterización**: crear `tests/test_estructura_artefactos.py` que falle si existe un `.py` bajo `test/`, si hay más de un `.sql`, si algún archivo de `test/` no es `.http` ni `.sql`, o si `pytest.ini` no declara `testpaths = tests`. Verificar: el test pasa sobre el estado actual (ya conforme) y falla al crear temporalmente un `test/foo.py` (luego eliminarlo).
- [x] 8.2 **Verde**: dejar `test/` con `salud.http`, `auth.http` y `seed.sql`; confirmar que toda la suite pytest sigue en `tests/`. Verificar: `pytest tests/test_estructura_artefactos.py -q` verde y `Get-ChildItem test -Filter *.py` sin resultados.
- [x] 8.3 **Triangular**: agregar al test la verificación de que `tests/` contiene `conftest.py` y al menos un `test_*.py`, para que la convención no se cumpla vaciando ambas carpetas. Verificar: pasa y falla si se mueve la suite fuera de `tests/`.

## 9. Verificación integral

- [x] 9.1 Correr `pytest -q` completo y comparar con la línea base de 1.1. Verificar: 0 fallos nuevos, 0 warnings de sesión abierta y ningún test que escape de la transacción de prueba.
- [x] 9.2 Volver a correr `alembic check` y revisar `migrations/versions/`. Verificar: no hay migración nueva; si el apply necesitó una, el design debe actualizarse y la migración ser una tarea separada revisada a mano.
- [x] 9.3 Auditoría de reglas duras por búsqueda: sin `HTTPException` en `app/modules/usuarios/`; sin `commit()` en `router.py`/`service.py`/`repository.py`; handlers `async def`; schemas de entrada con `extra="forbid"`; sin `lazy` implícito; sin `hash_password_sync` en handlers. Verificar: los greps quedan vacíos y se registran en la revisión.
- [x] 9.4 Matriz de cobertura requisito→test: mapear cada escenario del delta `autenticacion-sesion` (incluidos los dos requisitos ADDED, el escenario de no fuga y el MODIFIED de auditoría) a al menos un test y anotar el nombre del test junto al requisito. Verificar: ningún escenario queda sin test.
- [x] 9.5 Verificar el contrato manual: ejecutar los requests de `test/auth.http` contra la API levantada y confirmar `200`, `401` y `422` con los cuerpos documentados. Verificar: las respuestas coinciden con la tabla de D2 del design y el `422` no repite contraseñas.

## Workflow follow-up

- Confirmar con un humano las decisiones de governance ALTO de `design.md`: no reemitir cookie tras el cambio, límite transaccional local pre-C-14, propagación de fallos de auditoría, política de complejidad 8–72 y saneamiento global del `422`.
- Archivar el change con `/opsx:archive password-lifecycle` después de la revisión.
- Durante el archive se sincroniza `autenticacion-sesion` a `openspec/specs/` y luego se marca `[C-11]` como `[x]` en `CHANGES.md`.
