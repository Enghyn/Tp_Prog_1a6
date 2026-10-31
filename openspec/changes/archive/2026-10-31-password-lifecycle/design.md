# Design

## Context

Ver `proposal.md` — Why. Estado relevante del repositorio al iniciar este change:

- `app/modules/usuarios/router.py` ya expone `router_publico` (`/auth/login`, `/auth/logout`) y `router_autenticado` (`/auth/yo`); este último se monta en `router_protegido` de `main.py`, que aplica `requiere_password_actualizada`.
- `app/core/dependencies.py` ya implementa `obtener_usuario_actual` y `token_anterior_al_cambio(iat, password_cambiada_en)` con comparación estricta y precisión de microsegundos (RN-07). El gate RN-06 exime por prefijo `/auth/*` y `/health/*`; un endpoint bajo `/auth` queda accesible con `debe_cambiar_password=true`.
- `app/core/seguridad.py` provee `hash_password(contrasena, app_state)` (async, `to_thread` + semáforo), `verify_password_async(contrasena, hash, app_state)` y `verify_password_o_dummy(...)`. El semáforo vive en `app.state.bcrypt_semaforo`.
- `app/modules/usuarios/models.py` ya tiene `password_hash`, `password_cambiada_en: datetime | None` con `DateTime(timezone=True)` y `debe_cambiar_password: bool`.
- `app/core/database.py` expone `get_session` (sin `commit()`) y `session_maker`. `obtener_sesion_auditoria` crea una sesión independiente desde `request.app.state.session_maker`.
- `main.py` responde a `RequestValidationError` con `exc.errors()` tal cual. En Pydantic 2.7 cada error incluye `input` con el valor enviado (o el body completo en errores de modelo), por lo que un `422` puede repetir contraseñas; C-11 endurece ese handler (D10).
- No existe `UnitOfWork` (C-14) ni la jerarquía de repositorios (C-13). `get_session` no commitea y la sesión del request ya tiene una transacción autobegin por el `sesion.get` de `obtener_usuario_actual`.
- `tests/conftest.py` ya overridea `get_session` y `obtener_sesion_auditoria` en `contexto_auth` con una conexión externa y `join_transaction_mode="create_savepoint"`.

Restricciones que mandan: reglas duras #1 (solo `AppError`), #2 (sin `commit()` en handlers ni repositorios), #3 (`lazy="raise"` + precarga explícita), #5 (bcrypt fuera del event loop), #6 (`async def`), #7 (`extra="forbid"`), #8 (sin migración sin justificar), #9 (PostgreSQL real), #13 (type hints y `snake_case`), #15 (`test/` solo `.http` + un `.sql`; `tests/` para pytest).

## Goals / Non-Goals

**Goals:**

- Cerrar el ciclo de vida de la contraseña: cambiarla, limpiar `debe_cambiar_password` y hacer efectiva la invalidación RN-07 que C-09 solo sabía verificar.
- Mantener un único contrato de error uniforme y opaco, reutilizando `NoAutenticadoError` y el handler global.
- Persistir el cambio de forma atómica sin introducir un `UnitOfWork` prematuro ni duplicar la jerarquía de C-13/C-14.
- Dejar la suite preparada para que C-14 reemplace el límite transaccional sin cambiar el contrato HTTP.

**Non-Goals:**

- Reemitir un token nuevo tras el cambio. RN-07 exige que el token usado quede inválido; el cliente vuelve a loguearse.
- Revocación server-side de tokens o lista negra. El modelo sigue siendo *stateless* + `password_cambiada_en`.
- Recuperación de contraseña por email, expiración periódica de contraseñas o historial de hashes.
- Gestión administrativa de usuarios y roles (C-12), `UnitOfWork` (C-14) y `BaseRepository` (C-13).
- Migración de esquema: las tres columnas ya existen en `001_auth_core`.

## Decisions

### D1: Ubicación de los artefactos

- `app/modules/usuarios/schemas.py`: `SolicitudCambioPassword` y `RespuestaCambioPassword`.
- `app/modules/usuarios/repository.py`: `obtener_sesion_cambio_password` (dependency de sesión dedicada) y `actualizar_password(...)` (un único `UPDATE`).
- `app/modules/usuarios/service.py`: `cambiar_password(...)` con la orquestación verificar → hashear → persistir → auditar.
- `app/modules/usuarios/router.py`: handler `POST /auth/cambiar-password` en `router_autenticado`, con `request` para obtener la IP de auditoría.
- `main.py`: handler de `RequestValidationError` endurecido para no repetir secretos (D10).

**Rationale**: la KB 06 §2 asigna los endpoints de auth al módulo `usuarios`; el proyecto ya concentra schemas, repository, service y router ahí. No se crea un módulo `auth` paralelo; `main.py` solo se toca para endurecer el handler de validación (D10), no para el wiring de routers.

**Alternativa descartada**: montar el endpoint en `router_publico` y resolver la sesión manualmente dentro del handler. Duplicaría `obtener_usuario_actual` y rompería la separación de grupos de C-10.

### D2: Contrato HTTP exacto

```http
POST /auth/cambiar-password
Cookie: access_token=<jwt>

{"password_actual": "Provisoria1", "password_nueva": "NuevaClave2"}
```

| Caso | Código | Cuerpo |
|------|--------|--------|
| Éxito | `200` | `{"detail": "Contraseña actualizada"}` |
| `password_actual` no verifica | `401` | `{"detail": "Credenciales inválidas", "codigo": "CREDENCIALES_INVALIDAS"}` |
| Sin cookie / token inválido | `401` | mismo cuerpo uniforme |
| Contrato o política incumplidos | `422` | `{"detail": [...], "codigo": "ERROR_VALIDACION"}` con `loc`/`msg`/`type` y **sin** `input`/`ctx` |

**Rationale**: la KB 06 §2 fija `200`, `401` y `422`, pero no el body; se adopta `password_actual`/`password_nueva` por consistencia con el campo `password` de `SolicitudLogin` y se documenta la decisión. El `401` reutiliza exactamente el cuerpo del login para no distinguir causas.

**Alternativa descartada**: `contrasena_actual`/`contrasena_nueva`. Las funciones de `seguridad.py` usan `contrasena`, pero los schemas HTTP ya usan `password`; mezclar ambos vocabularios en el mismo contrato es peor.

### D3: Orden de operaciones y bcrypt fuera del event loop

```text
1. FastAPI valida SolicitudCambioPassword (422 si falla) y resuelve la sesión (401 si falta).
2. ip = request.client.host if request.client else "desconocida".
3. service verifica password_actual con verify_password_async(password_actual, usuario.password_hash, app_state)
   → si False: NoAutenticadoError uniforme, sin tocar la base.
4. service calcula el hash nuevo con hash_password(password_nueva, app_state)
   → to_thread + semáforo; nunca hash_password_sync.
5. ahora = datetime.now(timezone.utc)   # después del hash, antes del UPDATE
6. UPDATE atómico (D4).
7. auditar_acceso(sesion_auditoria, RegistroAcceso(email=usuario.email, ip=ip,
   actor=usuario.email, accion="PASSWORD_CAMBIADA", exito=None, cuando=ahora)).
8. 200 {"detail": "Contraseña actualizada"}.
```

**Rationale**: el hash se calcula antes de abrir la transacción de escritura (mismo criterio que C-17) para no retener una conexión durante bcrypt. `ahora` se captura después del hash para que cualquier token emitido durante el cálculo quede también invalidado; es la opción conservadora.

**Alternativa descartada**: capturar `ahora` al inicio del request. Un token emitido mientras se hashea la nueva contraseña quedaría con `iat` posterior y sobreviviría al cambio.

### D4: Persistencia atómica sin adelantar el Unit of Work

**Decisión**: el endpoint recibe una sesión dedicada mediante `obtener_sesion_cambio_password` (misma forma que `obtener_sesion_auditoria`, leyendo `request.app.state.session_maker` con fallback al `session_maker` global) y el service ejecuta:

```python
async with sesion_cambio.begin():
    await actualizar_password(
        sesion_cambio,
        usuario_id=usuario.id,
        password_hash=nuevo_hash,
        cambiada_en=ahora,
    )
```

`actualizar_password` ejecuta un único `UPDATE usuario SET password_hash=..., password_cambiada_en=..., debe_cambiar_password=false WHERE id=...` y verifica `rowcount == 1`; no hace `commit()` ni cierra la sesión. El instante `cambiada_en` se pasa como parámetro (no se calcula dentro del repositorio), de modo que el test puede fijarlo con microsegundos exactos.

**Rationale**: la sesión del request ya tiene una transacción autobegin (por `obtener_usuario_actual`), por lo que `async with sesion.begin()` sobre ella fallaría. La sesión dedicada no comparte identidad ni transacción con la del request, y `begin()` confirma o revierte el bloque completo sin que el handler ni el repositorio llamen a `commit()`.

**Deuda técnica declarada**: la regla dura #2 reserva el commit al `UnitOfWork`. C-11 corre antes de C-14 (GATE 6), así que este bloque es un límite transaccional local y temporal, limitado a una sola escritura de dominio. C-14 lo reemplazará por `UnitOfWork.__aexit__` sin cambiar el contrato HTTP ni los tests de comportamiento. Se deja un `TODO(C-14)` junto al bloque.

**Por qué no se reutiliza `obtener_sesion_auditoria`**: su design (C-09, D3) prohíbe explícitamente usarla para escrituras de dominio; mezclar ambas responsabilidades haría que un fallo de auditoría y un fallo de persistencia compartieran sesión.

**Alternativa descartada**: `await sesion.commit()` en el service. Viola la regla dura #2 de forma directa y deja la transacción del request en un estado difícil de razonar.

**Alternativa descartada**: crear `app/core/unit_of_work.py` en este change. Adelanta C-14, obliga a diseñar la interfaz de repositorios de C-13 y desborda el alcance de un change atómico.

### D5: RN-07 — timestamp con microsegundos y sin reemitir cookie

`password_cambiada_en` se persiste con `datetime.now(timezone.utc)` sin `replace(microsecond=0)` ni truncados. La comparación existente (`iat < password_cambiada_en`) ya es estricta y con microsegundos.

El endpoint **no** emite un token nuevo: la cookie actual queda inválida por diseño. El flujo esperado es login con contraseña provisoria → cambio → login con la nueva. Esto mantiene una sola fuente de emisión de tokens (`POST /auth/login`) y evita duplicar la lógica de roles/`iat`.

**Consecuencia para tests**: el test de éxito debe usar el token viejo y comprobar `401`; luego hacer login con la nueva contraseña y comprobar `200` en una ruta protegida.

### D6: Auditoría `PASSWORD_CAMBIADA`

Se reutiliza `auditar_acceso(sesion_auditoria, RegistroAcceso(email=usuario.email, ip=ip, actor=usuario.email, accion="PASSWORD_CAMBIADA", exito=None, cuando=ahora))` para que escriba solo `evento_seguridad` (sin fila en `intento_acceso`). La IP se toma de `request.client.host` con fallback `"desconocida"`, igual que en el login. La sesión de auditoría es la dependency existente `obtener_sesion_auditoria`.

**Orden**: auditoría después del `UPDATE` confirmado. Si la auditoría falla, la excepción se propaga (500) y la contraseña ya cambió; se acepta porque la integridad de la contraseña es prioritaria y el evento es trazabilidad, no autorización. Es la misma política de C-09 (D13).

**Alternativa descartada**: auditar antes del `UPDATE`. Registraría un cambio que puede no haberse persistido.

### D7: Política de contraseña y `422`

`SolicitudCambioPassword` usa `ConfigDict(extra="forbid")`, `password_actual: str = Field(min_length=1, max_length=72)` y `password_nueva: str = Field(min_length=8, max_length=72)`. Un `field_validator` exige al menos una mayúscula ASCII, una minúscula ASCII y un dígito; un `model_validator(mode="after")` rechaza `password_nueva == password_actual`. Las contraseñas **no** se normalizan con `strip`: los espacios son parte del secreto y deben compararse tal cual.

**Rationale**: 72 es el límite de bcrypt y ya se usa en `SolicitudLogin`; 8 es el mínimo razonable para una contraseña definitiva. Al vivir en el schema, el `RequestValidationError` existente produce `422` sin lógica extra en el handler.

**Limitación aceptada**: `max_length` cuenta caracteres, no bytes; una contraseña no ASCII de 72 caracteres puede superar los 72 bytes de bcrypt. Es la misma limitación que ya tiene el login y no se corrige en este change.

**Alternativa descartada**: validar la complejidad en el service. Produciría un `ReglaNegocioError` (`422` pero con `codigo="REGLA_NEGOCIO"`) y rompería la uniformidad del contrato de validación.

### D8: Invariante de carpetas `test/` vs `tests/`

Se agrega `tests/test_estructura_artefactos.py` que verifica, sobre el árbol real:

- no existe ningún archivo `.py` bajo `test/`;
- `test/` contiene exactamente un archivo `.sql`;
- todo archivo de `test/` que no sea `.sql` termina en `.http`;
- `pytest.ini` declara `testpaths = tests`.

**Rationale**: la convención ya está documentada en `AGENTS.md` (regla dura #15) y `CHANGES.md`, pero nada la protege. El test es barato, corre sin base de datos y convierte una convención social en un contrato verificable. El nuevo `test/auth.http` cumple la regla; no se mueve ningún archivo porque la carpeta ya es conforme.

**Alternativa descartada**: un script de CI separado. El proyecto no tiene CI y `pytest` es el único gate que ya se ejecuta.

### D9: Errores y opacidad

- Contraseña actual incorrecta → `NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")`, el mismo objeto que usa el login.
- `rowcount != 1` en el `UPDATE` → `NoAutenticadoError` uniforme (el usuario pudo ser borrado entre la resolución y la escritura; no se revela el motivo).
- Nunca se usa `HTTPException` ni se expone el nombre de una constraint.

### D10: El `422` no repite contraseñas

**Decisión**: el handler de `RequestValidationError` de `main.py` deja de devolver `exc.errors()` crudo y responde solo con `loc`, `msg` y `type` de cada error (sin `input` ni `ctx`). Se agrega un test de regresión para login y para cambio de contraseña que verifica que el cuerpo del `422` no contiene la contraseña enviada.

**Rationale**: en Pydantic 2.7, cada error incluye `input` con el valor enviado o el body completo; en un `422` por contraseña corta o por un campo faltante, el cuerpo de la respuesta repetiría `password_actual`/`password_nueva`. Es una fuga de secretos, no un detalle de estilo. El contrato de `http-contracts` se mantiene: sigue siendo una lista de errores de validación con campo, mensaje y tipo.

**Alternativa descartada**: redactar solo los campos cuyo nombre empiece con `password`. Es frágil: los errores de modelo incluyen el body completo y cualquier cambio de nombre dejaría la fuga abierta.

## Risks / Trade-offs

- **[Fuga de contraseñas en el `422`]** → Mitigado por D10: el handler devuelve solo `loc`/`msg`/`type` y un test de regresión verifica que no aparezcan las contraseñas.
- **[Consumidores que leían `input` en el `422`]** → El contrato de `http-contracts` solo exige la lista de errores; los tests existentes verifican códigos, no `input`. Se documenta el cambio en el README.
- **[Test de microsegundos frágil]** → El instante `cambiada_en` se pasa como parámetro y el test lo fija con microsegundos exactos; no se depende de que `datetime.now()` caiga en un microsegundo distinto de cero.
- **[Dos escrituras no atómicas: contraseña y auditoría]** → Se acepta: la contraseña se confirma antes de auditar y un fallo de auditoría devuelve `500` con el cambio ya persistido. Se documenta en el design y se cubre con un test que verifica la propagación.
- **[El límite transaccional local contradice parcialmente la regla dura #2]** → Se acota a una sola escritura, se marca `TODO(C-14)` y se agrega una tarea de verificación que falla si aparece un `commit()` explícito.
- **[Carrera entre dos cambios de contraseña concurrentes]** → Última escritura gana. La concurrencia optimista está fuera de alcance (capítulo 7) y se documenta como limitación aceptada.
- **[Un token emitido justo antes del `UPDATE` queda inválido]** → Es el comportamiento buscado por RN-07; el usuario debe reautenticarse.
- **[Contraseñas no ASCII cerca del límite de bcrypt]** → Misma limitación que el login; se documenta y no se corrige en C-11.
- **[El test guardián de carpetas puede volverse ruidoso si se agregan fixtures binarios]** → Se limita a extensiones, no a contenido; un `.sql` adicional se detecta a propósito.

## Migration Plan

No hay migración de base de datos: `001_auth_core` ya crea `password_hash`, `password_cambiada_en` y `debe_cambiar_password`. El despliegue es un cambio de código sin pasos de datos. Rollback: revertir el endpoint y las funciones nuevas; las columnas y los datos existentes no se alteran.

## Open Questions

Ninguna bloqueante. Quedan como supuestos registrados: el body `password_actual`/`password_nueva`, la política 8–72 con mayúscula/minúscula/dígito y la no reemisión de cookie. Si el docente exige otro contrato, se ajusta el delta y los tests antes del apply.
