# Design

## Context

Ver `proposal.md` — Why. Estado relevante del repositorio al iniciar este change:

- `app/core/configuracion.py` ya expone `jwt_secret` (obligatorio y validado), `access_token_ttl_min=60`, `bcrypt_max_concurrency=4`, `login_max_intentos=5`, `login_ventana_seg=60` y `entorno="dev"`. **No hace falta agregar configuración.**
- `app/core/seguridad.py` provee `hash_password`, `verify_password_async`, `hash_password_sync`, `generar_hash_ficticio` y `verify_password_o_dummy(contrasena, hash_real, hash_ficticio, app_state)`. El semáforo de bcrypt vive en `app.state.bcrypt_semaforo`, creado en el `lifespan` de `main.py`.
- `app/core/database.py` expone `get_session` (sin `commit()`), `session_maker` a nivel de módulo y `crear_fabricante_sesion`.
- `app/core/errors.py` ya define `ErrorAplicacion` y `DemasiadasPeticionesError(reintentar_despues)`; el handler de `main.py` ya traduce `retry_after` a la cabecera `Retry-After`. **No hay que tocar el handler de errores.**
- `app/modules/usuarios/models.py` ya tiene `Usuario`, `AsignacionRol`, `IntentoAcceso` y `EventoSeguridad`; `Usuario.asignaciones` y `AsignacionRol.usuario` usan `lazy="raise"`.
- Migración `001_auth_core` ya crea el índice `ix_intento_acceso_email_ip_cuando (email, ip, cuando)`.
- `tests/conftest.py` overridea `get_session` con una sesión ligada a una transacción externa con `join_transaction_mode="create_savepoint"` y hace `rollback` al final del test.

Restricciones que mandan sobre el diseño: reglas duras #1 (sólo `AppError`), #2 (sin `commit()` en handlers — con la excepción documentada de auditoría), #3 (`lazy="raise"` + `selectinload`), #4 (roles del token no autorizan), #5 (bcrypt fuera del loop), #6 (`async def`), #7 (`extra="forbid"`), #8 (sin migración sin justificar), #9 (PostgreSQL real), #10 (sin colas), #13 (type hints + `snake_case`).

## Goals / Non-Goals

**Goals:**

- Un único punto de emisión de sesión (`POST /auth/login`) y un único punto de resolución (`obtener_usuario_actual`), reutilizable por C-10, C-11 y todos los módulos de dominio.
- Que el estado del rate limit viva exclusivamente en `intento_acceso` (PostgreSQL), de modo que sobreviva reinicios y sea observable/auditable.
- Que el registro de auditoría sea inmune al resultado de la petición (commit propio).
- Que la invalidación por cambio de contraseña funcione con precisión de microsegundos sin tocar `password_cambiada_en` (eso es C-11).

**Non-Goals:**

- Autorización por rol, `require_roles`, separación de grupos de rutas y gating de `debe_cambiar_password` (C-10).
- `POST /auth/cambiar-password` (C-11) y `POST /auth/registro` (C-17).
- Jerarquía `BaseRepository` / `UnitOfWork` (C-13/C-14). Este change implementa consultas mínimas y locales.
- Archivos `.http` de integración y smoke E2E (C-20).
- Revocación server-side de tokens (lista negra). El modelo es *stateless* + `password_cambiada_en`.

## Decisions

### D1: Ubicación de los artefactos (estructura de 6 capas)

- `app/modules/usuarios/schemas.py`: `SolicitudLogin`, `RespuestaSesion`, `RespuestaYo`.
- `app/modules/usuarios/repository.py`: funciones `async` de lectura/escritura sobre `AsyncSession` (`buscar_usuario_por_email`, `contar_intentos_fallidos`, `registrar_intento`, `registrar_evento`).
- `app/modules/usuarios/service.py`: `ServicioAutenticacion` o funciones `async` con la orquestación (rate limit → verificación → emisión → auditoría).
- `app/modules/usuarios/router.py`: `APIRouter()` con `/auth/login`, `/auth/logout`, `/auth/yo`, montado en `main.py`.
- `app/core/dependencies.py` (**nuevo**): `obtener_usuario_actual`; C-10 extiende el mismo archivo con `get_roles_vigentes` y `require_roles`.
- `app/core/seguridad.py`: se le agregan `crear_token_acceso(...)`, `decodificar_token_acceso(...)` y `construir_cookie_sesion(...)`.

**Rationale**: AGENTS.md fija `app/core/` (config, security, errors, dependencies, db) y `app/modules/<dominio>/` (router, schemas, service, repository, models). La KB 06 §2 asigna los endpoints de auth al módulo `usuarios`. Mantener JWT en `seguridad.py` evita un módulo `tokens.py` fuera del layout declarado.

**Alternativa descartada**: `app/core/tokens.py` o `app/modules/auth/` — crearía un séptimo espacio de nombres no previsto por el proyecto y duplicaría el módulo `usuarios` que ya contiene los modelos.

### D2: Consultas mínimas en `repository.py` en lugar de la jerarquía de repositorios

**Decisión**: `repository.py` contiene **funciones** `async` que reciben `AsyncSession` y ejecutan `select()`/`insert()`; no se crean clases ni `BaseRepository`.

**Rationale**: C-13 define `BaseRepository[T]` y declara explícitamente el "refactor de `app/modules/usuarios` (C-09/C-12) para consumir los repositorios sin cambiar contratos HTTP". Crear ahora una jerarquía paralela obligaría a escribirla dos veces. Las funciones sí respetan la separación de capas (el router no construye SQL) y son el punto exacto que C-13 reemplaza.

**Alternativa descartada**: SQL embebido en `service.py` — rompe la estructura de 6 capas y haría el refactor de C-13 más invasivo.

### D3: Transacción independiente para `intento_acceso` / `evento_seguridad` (excepción a la regla dura #2)

**Decisión**: la auditoría se escribe en una sesión **propia**, obtenida de una dependency `obtener_sesion_auditoria()` que construye una sesión nueva desde el `async_sessionmaker` (preferentemente `request.app.state.session_maker`), y se cierra con `async with sesion.begin(): ...` fuera del ciclo de vida de la sesión del request.

```text
request  ──► get_session (sesión A, sin commit)
                 └─ lectura de usuario y conteo de intentos (sólo SELECT)
             obtener_sesion_auditoria (sesión B)
                 └─ async with B.begin():  INSERT intento_acceso + INSERT evento_seguridad
                 └─ commit SIEMPRE (antes del raise del 401 o del 429)
```

**Rationale (KB 09 §5, RN-08)**: si la auditoría compartiera la transacción del request, el `401` (que en este design se materializa como excepción de dominio) provocaría el `rollback` del UoW y borraría el intento fallido; el rate limit dejaría de funcionar. La sesión B es independiente de verdad: no es un `SAVEPOINT` de A, porque un `rollback` de A también revertiría los savepoints.

**Por qué esto no contradice la regla dura #2**: la regla prohíbe `commit()` en repositorios y handlers y reserva el commit al `UnitOfWork`. Acá el commit lo ejecuta el contexto `begin()` de una sesión de auditoría propiedad del helper `auditar_acceso()`, que no es la sesión de dominio ni forma parte del UoW del request. Es la única excepción autorizada por KB 09 §5, está limitada a tablas append-only de seguridad (`intento_acceso`, `evento_seguridad`) y **no debe usarse para escrituras de dominio**; C-14 la documentará como "sub-UoW de auditoría".

**Consecuencia para tests**: `tests/conftest.py` debe overridear también `obtener_sesion_auditoria`, apuntando a un `sessionmaker` ligado a la misma conexión externa con `join_transaction_mode="create_savepoint"`. Si no se overridea, los tests escribirían con una conexión distinta: las filas escaparían del `rollback` del test y se contaminaría la base entre ejecuciones. Esta fixture es parte del alcance (no es sólo plumbing de test: demuestra que la sesión B es independiente y a la vez controlable).

**Alternativa descartada**: `AUTOCOMMIT` o `session.execute(text("COMMIT"))` sobre la sesión A — corrompe la semántica del UoW y rompe el aislamiento del test.

### D4: Orden exacto de operaciones del login y semántica del umbral

```text
1. resolver ip = request.client.host (o "desconocida")
2. ahora = datetime.now(timezone.utc)
3. contar fallos de (email, ip) con cuando >= ahora - login_ventana_seg y exito = false
4. si fallos >= login_max_intentos:
       auditoría independiente → evento LOGIN_BLOQUEADO (sin INSERT en intento_acceso)
       raise DemasiadasPeticionesError(..., reintentar_despues=<D5>)
5. buscar usuario por email (selectinload de asignaciones)
6. ok = await verify_password_o_dummy(password, hash_real | None, app.state.hash_ficticio, app.state)
7. auditoría independiente → intento_acceso(exito=ok) + evento (LOGIN_OK | LOGIN_FALLIDO)
8. si not ok o usuario inexistente o not usuario.activo → raise NoAutenticadoError("Credenciales inválidas", "CREDENCIALES_INVALIDAS")
9. emitir token, construir cookie, devolver 200
```

**Decisión sobre el umbral**: se bloquea cuando el conteo **previo** ya es `>= login_max_intentos`. Es decir, con `login_max_intentos=5`: los fallos 1..5 se verifican con bcrypt y responden `401`; la **sexta** petición dentro de la ventana responde `429`.

**Rationale**: es la lectura literal del contrato de C-09 ("si ≥ 5 → 429") y la única que no bloquea a un usuario con 4 fallos y contraseña correcta en el 5º intento. La línea de tests de CHANGES ("quinto fallo → 429") es ambigua y se interpreta como "una vez registrados los 5 fallos, la petición siguiente se bloquea"; el escenario "El intento que alcanza el límite todavía se verifica" fija esta semántica en el delta. **Queda marcada para confirmación humana** (governance CRÍTICO) porque cambia el número de intentos efectivos.

**Decisión sobre las peticiones bloqueadas**: **no** insertan una fila en `intento_acceso`. Si lo hicieran, cada reintento dentro del bloqueo reiniciaría la ventana (o la extendería) y el bloqueo se autoalimentaría indefinidamente; además inflaría la tabla. Sólo se registra `LOGIN_BLOQUEADO` en `evento_seguridad`, que es justamente el rastro que pide el scope.

### D5: Cálculo de `Retry-After`

**Decisión**: `Retry-After` es un entero de segundos hasta que el bloqueo deja de aplicar:

```text
ultimos = los login_max_intentos fallos más recientes de la ventana (cuando ASC)
liberacion = ultimos[0].cuando + login_ventana_seg        # el más antiguo de los que sostienen el bloqueo
retry_after = max(1, ceil((liberacion - ahora).total_seconds()))
retry_after = min(retry_after, login_ventana_seg)
```

**Rationale**: cuando el fallo más antiguo del conjunto que sostiene el bloqueo sale de la ventana, el conteo baja a `login_max_intentos - 1` y el login vuelve a procesarse. Acotar a `[1, login_ventana_seg]` evita `0` (que invitaría a reintentar en el acto) y valores absurdos por desfase de reloj. Se reutiliza `DemasiadasPeticionesError(reintentar_despues=...)`; el handler existente ya emite `Retry-After: <n>`.

**Alternativa descartada**: `Retry-After` como HTTP-date — válido por RFC 9110, pero más difícil de testear y de consumir para el cliente de este TP.

### D6: Forma de `iat` y comparación con `password_cambiada_en` (RN-07)

**Decisión**: `iat` se emite como **string ISO-8601 en UTC con microsegundos** (`"2026-10-30T12:34:56.123456+00:00"`), no como *numeric date* entero. `exp` sí se emite como entero (*numeric date*, segundos), porque la expiración tiene semántica de segundo.

**Rationale**: PyJWT convierte a entero cualquier `datetime` que reciba en `iat`, perdiendo microsegundos; RN-07 exige comparar sin truncar. Con `password_cambiada_en` en `timestamptz` (precisión de microsegundos en PostgreSQL) y `iat` como string, la comparación `iat < password_cambiada_en` es exacta.

**Lectura defensiva**: al decodificar, `iat` se interpreta como `datetime.fromisoformat(...)`; si llegara como entero (token viejo o de otro emisor) se convierte con `datetime.fromtimestamp(valor, tz=timezone.utc)`. Cualquier `iat` no parseable → `401`. Comparación estricta: `iat < password_cambiada_en` invalida; `iat >= password_cambiada_en` es válido (un token emitido en el mismo instante del cambio sobrevive).

**Alternativa descartada**: `iat` entero + comparación con `password_cambiada_en.replace(microsecond=0)` — pierde precisión y puede invalidar tokens legítimos o aceptar tokens previos dentro del mismo segundo.

### D7: Atributos de la cookie y `secure` por entorno

**Decisión**: `construir_cookie_sesion(token, configuracion)` produce:

| Atributo | Valor |
|---|---|
| nombre | `access_token` |
| `httponly` | `True` |
| `samesite` | `"lax"` |
| `path` | `"/"` |
| `max_age` | `access_token_ttl_min * 60` |
| `secure` | `entorno.strip().lower() not in {"dev", "local", "test"}` |

El logout usa `response.delete_cookie(...)` con **los mismos** `path`, `httponly`, `samesite` y `secure`; si no coinciden, el navegador conserva la cookie original.

**Rationale**: `SameSite=Lax` bloquea el envío cross-site en `POST` (mitigación CSRF básica) sin romper navegación normal; `HttpOnly` impide lectura desde JS (mitigación XSS de exfiltración). `secure=True` en producción es obligatorio sobre HTTPS; forzarlo en `dev` rompería las pruebas locales sobre `http://localhost` y `TestClient`. `entorno="test"` también queda en `False` para permitir smoke tests sin TLS.

**Alternativa descartada**: `SameSite=Strict` — rompe el retorno desde enlaces externos; `secure` fijo en `True` — inutiliza el entorno de desarrollo.

### D8: Identificación de la IP para el rate limit

**Decisión**: `ip = request.client.host if request.client else "desconocida"`. **No** se lee `X-Forwarded-For` ni `X-Real-IP`.

**Rationale**: esas cabeceras son trivialmente falsificables por el cliente si no hay un proxy de confianza que las reescriba, y confiar en ellas convertiría el rate limit en un control evadible (bastaría rotar el header). Con `ASGITransport` de httpx, `request.client` existe (`127.0.0.1`), así que los tests son deterministas.

**Consecuencia**: detrás de un reverse proxy todos los clientes compartirían IP y el límite sería global por email. Aceptado y documentado como limitación del TP (no hay proxy en el alcance).

### D9: Uniformidad del `401` y códigos de error

**Decisión**: un único error para todos los caminos de credenciales/sesión:

```python
NoAutenticadoError(detalle="Credenciales inválidas", codigo="CREDENCIALES_INVALIDAS")
```

Se usa igual para email inexistente, contraseña incorrecta, usuario inactivo, cookie ausente, firma inválida, token expirado e `iat` anterior al cambio de contraseña. El body resultante es `{"detail": "Credenciales inválidas", "codigo": "CREDENCIALES_INVALIDAS"}` (regla dura #1, sin `HTTPException`).

**Rationale**: RN-09 exige que no se pueda enumerar usuarios; distintos mensajes o distintos `codigo` por rama filtran información. Un único código también simplifica los tests de "respuesta idéntica".

**Nota**: no se agrega `WWW-Authenticate: Bearer`, porque la autenticación no viaja por `Authorization` sino por cookie; anunciar `Bearer` sería engañoso para el cliente.

### D10: Validación del token

**Decisión**:

```python
jwt.decode(
    token,
    configuracion.jwt_secret,
    algorithms=["HS256"],          # algoritmo fijado, no leído del header
    options={"require": ["exp", "iat", "sub"], "verify_exp": True, "verify_iat": True},
    leeway=0,
)
```

`ExpiredSignatureError` / `InvalidTokenError` (cualquier subclase) → `401` uniforme. **Rationale**: fijar `algorithms` evita el ataque de confusión de algoritmo (`alg: none`, HS/RS swap); `leeway=0` mantiene el comportamiento determinista que esperan los tests de expiración; `require` evita tokens sin los claims de los que depende RN-07.

### D11: Roles vigentes para `/auth/yo` (RN-04)

**Decisión**: `obtener_usuario_actual` carga el usuario con `selectinload(Usuario.asignaciones)` y devuelve un objeto `SesionActual` (usuario + claims). `/auth/yo` filtra en Python las asignaciones vigentes con `revocada_en is None and (vence_en is None or vence_en > ahora)` y devuelve sólo `rol`. **Los `roles` del token nunca se proyectan en la respuesta.**

**Rationale**: RN-04 exige releer la base en cada petición; `selectinload` cumple la regla dura #3 (nada de lazy loading) y evita N+1. Filtrar en Python sobre la colección ya precargada evita una segunda consulta; C-10 moverá el filtro a SQL en `get_roles_vigentes` para poder reutilizarlo en `require_roles`.

**Alternativa descartada**: devolver `claims["roles"]` — viola RN-04 y haría que un rol revocado siga "visible" hasta que expire el token.

### D12: Contrato de entrada del login

**Decisión**: `SolicitudLogin` con `model_config = ConfigDict(extra="forbid")`, `email: EmailStr`, `password: str = Field(min_length=1, max_length=72)`, y normalización `strip()` del email mediante `field_validator`. `max_length=72` se justifica por el límite de bcrypt (72 bytes); aceptar más produciría un truncamiento silencioso y contraseñas distintas equivalentes.

**Rationale**: regla dura #7 + convención de `http-contracts`. El `422` lo produce el handler existente de `RequestValidationError`.

**Nota**: el límite se declara en caracteres, no en bytes; para ASCII coincide con los 72 bytes de bcrypt. Una contraseña UTF-8 multibyte podría exceder 72 bytes con menos caracteres: se acepta como aproximación conservadora y no se valida a nivel de bytes para no romper la ergonomía.

### D13: Mapeo de auditoría (`actor`, `accion`) y política de fallo

**Decisión**:

| Evento | `actor` | Cuándo |
|---|---|---|
| `LOGIN_OK` | email del usuario | credenciales válidas y usuario activo |
| `LOGIN_FALLIDO` | email enviado en el cuerpo | email inexistente, contraseña incorrecta o usuario inactivo |
| `LOGIN_BLOQUEADO` | email enviado en el cuerpo | rate limit alcanzado |
| `LOGOUT` | email del usuario del token | logout con token válido |

`intento_acceso` se inserta para `LOGIN_OK` y `LOGIN_FALLIDO` (con `exito` correspondiente); **no** para `LOGIN_BLOQUEADO` (ver D4). `cuando` se fija en Python (`datetime.now(timezone.utc)`) para que el cálculo de la ventana y el valor persistido usen el mismo reloj; en `evento_seguridad` se deja el `server_default` de la base, salvo que el helper decida pasar el mismo instante para consistencia de la auditoría.

**Política de fallo**: si la transacción de auditoría falla, la excepción **se propaga**. No se silencia con `try/except` porque el registro es el mecanismo que sostiene RN-08: un login que responde `200` sin dejar rastro rompería el control de seguridad de forma invisible. Costo aceptado: una falla de base en la sesión B convierte la respuesta en `500`.

**Alternativa descartada**: *best effort* con log — mantiene la disponibilidad pero degrada RN-08 silenciosamente.

### D14: Sin migración nueva

**Decisión**: C-09 **no** produce migración. Se verifica con `alembic check` / `alembic revision --autogenerate` en seco que el modelo y el esquema siguen sincronizados.

**Rationale**: la consulta del rate limit filtra `WHERE email = ? AND ip = ? AND cuando >= ? AND exito = false`; el índice existente `(email, ip, cuando)` cubre el prefijo completo, y `exito` se resuelve como filtro sobre las filas ya acotadas por el rango temporal (dentro de una ventana de 60 s por email+IP el volumen es mínimo). No hay columnas nuevas: `intento_acceso` ya tiene `cuando`, `email`, `ip`, `exito`; `usuario` ya tiene `activo` y `password_cambiada_en`.

**Si en la implementación apareciera la necesidad de un índice parcial `(email, ip, cuando) WHERE exito = false`**: queda **fuera** de este change, se justifica en un design aparte y se ejecuta como tarea separada con su migración revisada a mano (regla dura #8). No se hace "por las dudas" ahora.

### D15: Forma de las respuestas

```jsonc
// POST /auth/login  → 200
{
  "usuario": {"id": 1, "email": "admin@taller.test", "nombre": "Admin", "debe_cambiar_password": false},
  "roles": ["ADMIN"],
  "token": {"iat": "2026-10-30T12:34:56.123456+00:00", "exp": 1761873296}
}

// GET /auth/yo → 200: misma forma (usuario, roles vigentes, token)
// POST /auth/logout → 200: {"detail": "Sesión cerrada"}
```

**Rationale**: el cliente necesita saber si debe cambiar la contraseña antes de operar (RN-06, que aplica C-10) y qué roles tiene; `password_hash` nunca se serializa. Se reutiliza el mismo schema `RespuestaSesion` para login y `/auth/yo` para que no existan dos contratos que se desincronicen.

### D16: `logout` sin autenticación obligatoria

**Decisión**: `POST /auth/logout` **no** depende de `obtener_usuario_actual`. Si hay cookie válida, intenta identificar al usuario y registra `LOGOUT`; si no, responde `200` igual.

**Rationale**: un logout que falla con `401` deja al cliente con la cookie puesta y sin forma de limpiarla. La operación es idempotente por naturaleza: el objetivo es borrar la cookie del navegador. La identificación es *best effort* y la auditoría se registra sólo cuando el actor es conocido.

### D17: Montaje del router y relación con C-10

**Decisión**: `main.py` hace `app.include_router(usuarios_router.router)` con las rutas ya prefijadas `/auth/...` dentro del módulo. **No** se crean todavía `router_publico` / `router_protegido`.

**Rationale**: la separación de grupos y el gating de `debe_cambiar_password` son el corazón de C-10; adelantarlos acá duplicaría trabajo y mezclaría dos governance distintos. `obtener_usuario_actual` es la pieza que C-10 consumirá.

## Risks / Trade-offs

- **[Riesgo] Ambigüedad del umbral 5 vs 6 intentos** → El diseño fija "5 fallos registrados + siguiente petición bloqueada" (D4) y lo declara en el delta. Requiere confirmación humana antes del apply; cambiarlo es un ajuste de una línea en el servicio y de dos escenarios.
- **[Riesgo] Condición de carrera en el conteo** → Dos logins concurrentes pueden leer ambos "4 fallos" y ambos verificar. Mitigación aceptada: el control es *best effort* por ventana; la concurrencia avanzada (bloqueos, cap. 7) está fuera de alcance según KB 10.
- **[Riesgo] Doble conexión por login** → la sesión de auditoría toma una segunda conexión del pool mientras la del request sigue abierta. Con `pool_size` por defecto (5) y `bcrypt_max_concurrency=4` es holgado. Mitigación: cerrar la sesión B inmediatamente después del `begin()`.
- **[Riesgo] Falla de auditoría ⇒ 500** → D13 prioriza no perder registros de seguridad. Si se prefiere disponibilidad, cambiar a log + continuar es una decisión de governance, no de código.
- **[Riesgo] `Secure` mal configurado** → si `ENTORNO=produccion` no se setea en el deploy, la cookie viajaría sin `Secure`. Mitigación: documentar en `.env.example`/README y testear ambos entornos.
- **[Riesgo] IP detrás de proxy** → rate limit global por email (D8). Documentado como limitación.
- **[Trade-off] `logout` no revoca el token** → un token copiado sobrevive hasta `exp`. Es consecuencia del modelo stateless; RN-07 es el único mecanismo de revocación previsto. Escenario explícito en el delta.
- **[Trade-off] Tests acoplados a PostgreSQL real** → el rate limit y los timestamps son load-bearing; no se puede simular con SQLite (regla dura #9). Si PostgreSQL no está disponible los tests se `skip` (convención existente del repo).
- **[Trade-off] `iat` como string** → se aparta de la práctica habitual de *numeric date*. Se documenta en D6 porque es la única forma de cumplir RN-07 con microsegundos.

## Migration Plan

1. No hay migración de esquema ni cambio de configuración: el deploy es sólo código nuevo (router + módulo) y `main.py`.
2. Rollback: quitar el `include_router` y los archivos nuevos; los datos de `intento_acceso`/`evento_seguridad` ya escritos son append-only y no requieren limpieza.
3. Orden de despliegue: desplegar primero y luego habilitar el cliente que use la cookie; no hay consumidores previos que romper.

## Notas para la revisión de governance (CRÍTICO)

Puntos que un humano debería confirmar antes del apply, porque son políticas de seguridad y no sólo implementación:

1. **Umbral del rate limit** (D4): ¿5 fallos registrados bloquean la petición siguiente, o el 5º intento debe responderse ya con `429`?
2. **Peticiones bloqueadas no se registran en `intento_acceso`** (D4): evita el bloqueo autoextendido, a costa de no contar los reintentos.
3. **Falla de la auditoría ⇒ la petición falla** (D13): prioriza integridad del registro sobre disponibilidad.
4. **`secure` derivado de `entorno`** (D7): ¿se acepta `ENTORNO=produccion` como única señal, o se quiere un flag explícito `COOKIE_SECURE`?
5. **Sin lectura de `X-Forwarded-For`** (D8): asumido que no hay proxy de confianza delante de la API.
