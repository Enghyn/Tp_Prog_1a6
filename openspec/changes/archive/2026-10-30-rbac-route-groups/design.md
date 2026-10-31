# Design

## Context

Ver `proposal.md` — Why. Estado relevante del repositorio al iniciar este change:

- `app/core/dependencies.py` ya expone `SesionActual` (`usuario`, `iat`, `exp`), `token_anterior_al_cambio` y `obtener_usuario_actual`, que resuelve el usuario desde la cookie `access_token`, valida `exp` y compara `iat` con `password_cambiada_en`. Hoy carga `selectinload(Usuario.asignaciones)`.
- `app/core/errors.py` define `NoAutenticadoError` (401) y `ProhibidoError` (403), ambos subclases de `ErrorAplicacion`; el handler de `main.py` los serializa como `{"detail", "codigo"}`.
- `main.py` hace `app.include_router(health_router.router)` y `app.include_router(usuarios_router.router)` de forma plana. No existen `router_publico` / `router_protegido`.
- `app/modules/usuarios/router.py` define `router = APIRouter(prefix="/auth")` con `POST /auth/login`, `POST /auth/logout` y `GET /auth/yo`. `/auth/yo` filtra en Python las asignaciones precargadas con `obtener_roles_vigentes(usuario.asignaciones, ahora)` (helper puro en `service.py`).
- `app/modules/usuarios/models.py`: `AsignacionRol(usuario_id, rol, desde, vence_en, revocada_en, otorgada_por)` con `CHECK rol IN (...)` e índice único parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL`.
- `app/modules/clientes/models.py`: `Cliente(usuario_id nullable, ...)` con índice único parcial `uq_cliente_usuario (usuario_id) WHERE usuario_id IS NOT NULL`; `Vehiculo(cliente_id, borrado_en, ...)`.
- `app/modules/ordenes/models.py`: `OrdenTrabajo(vehiculo_id, mecanico_id nullable, estado, ...)`.
- No existe `app/modules/clientes/repository.py` ni `app/modules/ordenes/repository.py`; ambos módulos sólo tienen `models.py`.
- `tests/conftest.py` ofrece `cliente` (httpx/ASGITransport) y `contexto_auth` (PostgreSQL real, transacción externa con `join_transaction_mode="create_savepoint"`, override de `get_session` y de `obtener_sesion_auditoria`). Los tests se `skip` si PostgreSQL no está disponible.
- `openspec/specs/autenticacion-sesion/spec.md` ya fija el contrato de `/auth/*` y el `401` uniforme. **Ese contrato no se modifica en este change.**

Restricciones que mandan sobre el diseño (AGENTS.md, reglas duras): #1 sólo `AppError`; #2 sin `commit()` en handlers ni repositorios; #3 `lazy="raise"` + `selectinload` explícito, sin N+1; #4 los roles del JWT nunca autorizan; #6 todos los handlers `async def`; #9 tests contra PostgreSQL real; #13 type hints y `snake_case`.

## Goals / Non-Goals

**Goals:**

- Un único punto de decisión de permisos reutilizable por cualquier router (`require_roles`) y un único punto de lectura de roles vigentes (`get_roles_vigentes`), de modo que C-12 y los módulos de dominio no reimplementen SQL de autorización.
- Que la autorización sea *fail-closed*: lo que no está declarado público exige sesión, y la ausencia de rol es `403` (no `404` silencioso ni bypass).
- Que el estado de autorización (roles, vencimiento, revocación, contraseña pendiente) se lea siempre de la base, con un solo reloj de referencia (el de la aplicación).
- Que los helpers de propiedad sean reutilizables por `/mis-vehiculos`, `/mis-ordenes` y la cancelación por dueño (C-15/C-16/C-18) sin acoplarlos a un modelo ORM cargado.

**Non-Goals:**

- Emitir o refrescar tokens, revocar tokens server-side o tocar el contrato de `/auth/*` (C-09, cerrado).
- Implementar `POST /auth/cambiar-password` (C-11): este change sólo *detecta* la bandera y bloquea.
- Implementar endpoints de dominio, incluidos `/mis-*` y `DELETE /usuarios/{id}/roles/{rol}` (C-12, C-15, C-16).
- Introducir `BaseRepository` / `UnitOfWork` (C-13/C-14). Acá se usan funciones `async` sobre `AsyncSession`, igual que en C-09, que C-13 reemplazará sin cambiar contratos.
- Cachear roles entre requests o memoizarlos en un store externo: contradice RN-04.

## Decisions

### D1: Ubicación de las piezas (contrato en `core`, SQL en el módulo dueño del dato)

**Decisión:**

| Pieza | Archivo | Rol |
|---|---|---|
| `get_roles_vigentes(sesion, usuario_id) -> list[str]` | `app/core/dependencies.py` (fachada) + `app/modules/usuarios/repository.py` (consulta) | Lectura de roles vigentes |
| `require_roles(*roles)` | `app/core/dependencies.py` | Factory de dependencia por router |
| `requiere_password_actualizada` | `app/core/dependencies.py` | Gating RN-06 |
| `es_duenio_de_vehiculo(sesion, usuario_id, vehiculo_id) -> bool` | `app/core/dependencies.py` (fachada) + `app/modules/clientes/repository.py` (consulta, archivo nuevo) | RN-17 |
| `es_duenio_de_orden(sesion, usuario_id, orden_id) -> bool` | `app/core/dependencies.py` (fachada) + `app/modules/ordenes/repository.py` (consulta, archivo nuevo) | RN-17 |
| `router_publico` / `router_protegido` | `main.py` | Montaje de grupos |

**Rationale**: CHANGES fija `app/core/dependencies.py` como el lugar de las dependencias de autorización y AGENTS.md fija que el SQL vive en la capa de repositorio del módulo dueño del dato. La fachada en `core` da una superficie de import estable para todos los routers; la consulta en `repository.py` evita que `core` dependa del esquema de tablas de dominio y deja el punto exacto que C-13 sustituye por repositorios tipados.

**Alternativa descartada**: SQL directo en `app/core/dependencies.py` — acopla el núcleo al esquema de `vehiculo`, `cliente` y `orden_trabajo`, y duplica el trabajo que C-13/C-14 van a ordenar.

**Alternativa descartada**: un módulo `app/modules/autorizacion/` — crea un séptimo espacio de nombres no previsto por la estructura obligatoria de 6 capas y separa la autorización de los modelos que consulta.

**Nota sobre la firma**: CHANGES escribe `get_roles_vigentes(usuario_id)`. La sesión se recibe como primer parámetro explícito (`sesion`, `usuario_id`) en lugar de resolverse con `Depends`: así la función se puede llamar desde `require_roles`, desde `/auth/yo` y desde tests unitarios sin pasar por el contenedor de FastAPI. La dependencia HTTP que la envuelve se construye en D4.

### D2: Forma de la consulta de roles vigentes

**Decisión**:

```sql
SELECT DISTINCT rol
FROM asignacion_rol
WHERE usuario_id = :usuario_id
  AND revocada_en IS NULL
  AND (vence_en IS NULL OR vence_en > :ahora)
ORDER BY rol
```

`ahora` es `datetime.now(timezone.utc)` calculado **en Python una vez por request** y enviado como parámetro. Se implementa con SQLAlchemy 2.0 (`select(AsignacionRol.rol).where(...).distinct().order_by(...)`) y `await sesion.execute(...)` / `.scalars().all()`.

**Rationale**:

- **Python y no `now()` de PostgreSQL**: dentro de la fixture `contexto_auth`, la sesión vive en una transacción externa; `now()` en PostgreSQL devuelve el inicio de esa transacción, no el instante de la petición. Un test de "rol vencido hace un segundo" quedaría congelado y no probaría nada. Además fija un único reloj: el mismo que usa `obtener_usuario_actual` para `iat` y el que usará C-12 para escribir `vence_en`.
- **`DISTINCT` defensivo**: el índice único parcial ya garantiza una asignación abierta por rol, pero `DISTINCT` evita duplicados si en el futuro se agrega una fuente de roles adicional. `ORDER BY rol` hace determinista la lista de `/auth/yo`.
- **`vence_en > ahora` estricto**: una asignación que vence exactamente en el instante evaluado ya no autoriza (coherente con "vigente hasta, sin incluir, el vencimiento").

**Alternativa descartada**: reutilizar `obtener_roles_vigentes(asignaciones, ahora)` de `service.py` filtrando la colección precargada — obliga a que todo consumidor tenga el agregado `Usuario` con `selectinload`, impide usarlo desde un router que sólo conoce `usuario_id`, y arrastra una precarga que ya no hace falta (D3).

### D3: `obtener_usuario_actual` deja de precargar asignaciones

**Decisión**: se elimina `selectinload(Usuario.asignaciones)` de `obtener_usuario_actual`. `/auth/yo` obtiene los roles con `get_roles_vigentes(sesion, usuario.id)`. El helper puro `obtener_roles_vigentes` de `service.py` se conserva sólo si el login lo necesita para los `roles` informativos del JWT; si no, se elimina y el login usa la misma consulta.

**Rationale**: hoy la precarga existe únicamente para que `/auth/yo` filtre en Python. Mantenerla y además consultar roles en `require_roles` produciría dos lecturas del mismo dato por request. La consulta nueva es indexada y devuelve sólo strings, sin materializar el agregado ni sus relaciones `lazy="raise"` (regla dura #3: no se dispara lazy loading porque no se navega ninguna relación).

**Riesgo controlado**: cualquier código que hoy navegue `usuario.asignaciones` fallaría con `lazy="raise"`. Se verificó que los únicos consumidores son `router.py` y `service.py` de `usuarios`, ambos dentro del alcance. La tarea de implementación incluye `grep` de `\.asignaciones` como verificación.

**Alternativa descartada**: mantener la precarga y filtrar en Python dentro de `get_roles_vigentes` — funciona, pero obliga a recibir el `Usuario` completo y deja dos caminos de lectura que pueden divergir.

### D4: Composición de `require_roles` sobre `obtener_usuario_actual`

**Decisión**:

```python
def require_roles(*roles: str) -> Callable[..., Awaitable[SesionActual]]:
    requeridos = frozenset(roles)
    desconocidos = requeridos - set(ROLES_VALIDOS)
    if desconocidos:
        raise ValueError(f"Roles desconocidos: {sorted(desconocidos)}")   # falla al importar

    async def verificar(
        sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
        sesion: Annotated[AsyncSession, Depends(get_session)],
    ) -> SesionActual:
        vigentes = await get_roles_vigentes(sesion, sesion_actual.usuario.id)
        if requeridos.isdisjoint(vigentes):
            raise ProhibidoError("Permisos insuficientes", "PERMISOS_INSUFICIENTES")
        return sesion_actual

    return verificar
```

Uso por router: `router = APIRouter(dependencies=[Depends(require_roles("ADMIN"))])`; uso por endpoint: `sesion: Annotated[SesionActual, Depends(require_roles("MECANICO"))]`.

**Rationale**:

- `require_roles` **envuelve** `obtener_usuario_actual` en lugar de duplicar la validación del token: el `401` (cookie ausente, firma inválida, `exp` vencido, usuario inactivo, `iat` anterior al cambio de contraseña) queda resuelto en un solo lugar y con un solo `codigo` (`CREDENCIALES_INVALIDAS`), tal como ya está especificado en `autenticacion-sesion`.
- Devolver `SesionActual` permite que el handler use el usuario autenticado sin volver a resolverlo; FastAPI cachea la dependencia por request (`use_cache=True`), así que el token se valida una sola vez aunque la ruta declare `require_roles` y el handler declare `obtener_usuario_actual`.
- `frozenset` + `isdisjoint` expresa "alguno de los roles" sin cortocircuitos ni orden accidental.
- Validar los roles en el momento de construir la dependencia convierte un typo (`"ADMN"`) en un error de arranque, no en un `403` permanente en producción. `ROLES_VALIDOS` ya existe en `app/modules/usuarios/models.py` y es la única fuente de verdad del catálogo.

**Alternativa descartada**: `require_roles` como decorador — no compone con la inyección de dependencias de FastAPI, no aparece en OpenAPI y no permite reutilizar la sesión ya abierta.

**Alternativa descartada**: leer `payload["roles"]` del JWT y sólo consultar la base cuando el claim no alcanza — es exactamente el bypass que RN-04 prohíbe (un rol revocado seguiría autorizando hasta el `exp`).

### D5: Grupos de rutas y gating de contraseña pendiente (RN-06)

**Decisión**: en `main.py`:

```python
router_publico = APIRouter()
router_protegido = APIRouter(dependencies=[Depends(requiere_password_actualizada)])
```

- `router_publico` incluye: `health_router.router` (`/health/live`, `/health/ready`), `usuarios_router.router_publico` (`POST /auth/login`, `POST /auth/logout`) y, cuando exista, `POST /auth/registro` (C-17).
- `router_protegido` incluye: `usuarios_router.router_autenticado` (`GET /auth/yo`) y, a futuro, todos los routers de dominio (C-12, C-15, C-16, C-18).
- `app.include_router(router_publico)` y `app.include_router(router_protegido)`.

`requiere_password_actualizada` se define como:

```python
async def requiere_password_actualizada(
    request: Request,
    sesion_actual: Annotated[SesionActual, Depends(obtener_usuario_actual)],
) -> None:
    ruta = request.url.path
    if ruta.startswith("/auth/") or ruta.startswith("/health/"):
        return
    if sesion_actual.usuario.debe_cambiar_password:
        raise ProhibidoError("Cambio de contraseña requerido", "CAMBIO_PASSWORD_REQUERIDO")
```

**Rationale**:

- **Un solo punto de exigencia de sesión**: cualquier router que se sume a `router_protegido` hereda `401` sin sesión y `403` con contraseña pendiente. No hay que recordar declarar la dependencia en cada endpoint, y olvidarla no deja la ruta abierta.
- **`401` antes que `403`**: `requiere_password_actualizada` depende de `obtener_usuario_actual`, que se resuelve primero. Sin cookie → `401`; con cookie válida y bandera activa → `403`. Es el orden que exige el spec.
- **Exención por prefijo de path**: RN-06 está enunciada como "salvo `/auth/*` y `/health/*`". Implementarla como exención de prefijo hace que C-11 (`POST /auth/cambiar-password`) funcione sin tocar `main.py` y sin una tercera lista de rutas que se desincronice. El namespace `/auth/` es exactamente el conjunto exento por la regla; cualquier ruta nueva ahí es, por definición, una ruta de autenticación.
- **`/auth/logout` queda en el grupo público**: C-09 fijó que el logout es idempotente y responde `200` incluso sin cookie o con token inválido (D16 de `auth-login-jwt`). Montarlo en `router_protegido` lo convertiría en `401` y dejaría al cliente con la cookie puesta. Es una desviación consciente de la enumeración literal de CHANGES (`router_publico` = `/health/*`, `/auth/registro`, `/auth/login`), se documenta acá y queda marcada para revisión de governance. No debilita la autorización: el logout sólo borra la cookie y no expone datos.
- **`/auth/yo` en el grupo protegido**: hereda el `401` del grupo y además su propia dependencia `obtener_usuario_actual` (cacheada, no se ejecuta dos veces). La exención de prefijo lo deja pasar el gating, como pide el spec.

**Alternativa descartada**: `FastAPI(dependencies=[...])` global — no permite excluir `/health/*` ni `/auth/login`, y obligaría a un `if` por path igualmente.

**Alternativa descartada**: tres grupos (`público`, `autenticado`, `protegido-con-gating`) — más explícito, pero CHANGES pide dos y la exención por prefijo cubre el caso de `/auth/yo` sin ambigüedad.

### D6: Helpers de propiedad (RN-17) como predicados puros sobre `usuario_id`

**Decisión**: ambos helpers son `async`, reciben `(sesion, usuario_id, recurso_id)` y devuelven `bool`. No levantan excepciones: el endpoint decide si un `False` es `403` o `404`, según su contrato. Las consultas usan `EXISTS` y no cargan entidades:

```sql
-- es_duenio_de_vehiculo
SELECT EXISTS (
  SELECT 1 FROM vehiculo v JOIN cliente c ON c.id = v.cliente_id
  WHERE v.id = :vehiculo_id AND c.usuario_id = :usuario_id
)

-- es_duenio_de_orden
SELECT EXISTS (
  SELECT 1 FROM orden_trabajo o
  JOIN vehiculo v ON v.id = o.vehiculo_id
  JOIN cliente c ON c.id = v.cliente_id
  WHERE o.id = :orden_id AND c.usuario_id = :usuario_id
)
```

**Rationale**:

- **Predicado y no dependencia HTTP**: `usuario_id` y el id del recurso vienen de la ruta, no siempre del `SesionActual` (por ejemplo, un ADMIN que consulta un vehículo ajeno no es "dueño"; un endpoint puede necesitar distinguir "no existe" de "no es tuyo"). Un `bool` deja esa decisión al contrato de cada endpoint.
- **`EXISTS` con joins**: una sola consulta, sin materializar `OrdenTrabajo`, `Vehiculo` ni `Cliente`. Evita el N+1 y el `lazy="raise"` de `Vehiculo.cliente` (regla dura #3), y usa índices por PK más `uq_cliente_usuario`.
- **`borrado_en` no se filtra**: la propiedad es histórica. Un cliente debe poder consultar una orden vieja cuyo vehículo fue dado de baja (RN-16 regula el alta de órdenes nuevas, no la lectura del historial). Filtrar `borrado_en` acá convertiría un vehículo de baja en "ajeno" y devolvería `403` en `/mis-ordenes`.
- **`mecanico_id` no otorga propiedad**: RN-17 es una regla del rol CLIENTE. El acceso del mecánico a una orden asignada se decide por rol (`require_roles("MECANICO")`) más la verificación de asignación que corresponde a C-16; mezclarlo acá haría que un mecánico pudiera "poseer" vehículos ajenos y rompería `/mis-vehiculos`.

**Alternativa descartada**: cargar el agregado con `selectinload` y comparar en Python — más caro, dispara relaciones y expone el modelo ORM fuera del repositorio.

**Alternativa descartada**: helpers que levanten `ProhibidoError` directamente — impide que un endpoint responda `404` cuando corresponde y acopla la política HTTP al predicado.

### D7: Códigos de error

**Decisión**:

| Situación | Excepción | HTTP | `codigo` |
|---|---|---|---|
| Sin cookie / token inválido / expirado / usuario inactivo / `iat` viejo | `NoAutenticadoError` (ya existente) | 401 | `CREDENCIALES_INVALIDAS` |
| Autenticado sin ninguno de los roles exigidos | `ProhibidoError("Permisos insuficientes", ...)` | 403 | `PERMISOS_INSUFICIENTES` |
| Autenticado con `debe_cambiar_password=true` en ruta no exenta | `ProhibidoError("Cambio de contraseña requerido", ...)` | 403 | `CAMBIO_PASSWORD_REQUERIDO` |
| Recurso ajeno detectado por un helper de propiedad | lo decide el endpoint (C-15/C-16) con `ProhibidoError` | 403 | `PERMISOS_INSUFICIENTES` |

**Rationale**: regla dura #1 (nada de `HTTPException` ad-hoc) y formato uniforme de `http-contracts`. Los dos `403` se distinguen por `codigo` porque el cliente necesita saber si debe cambiar la contraseña (`CAMBIO_PASSWORD_REQUERIDO`) o pedir permisos (`PERMISOS_INSUFICIENTES`); el `detail` no enumera los roles del usuario.

### D8: Sin migración de base de datos

**Decisión**: este change **no** genera migración Alembic.

**Rationale**:

- `asignacion_rol` ya tiene `usuario_id`, `rol`, `revocada_en` y `vence_en`; el índice único parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL` cubre el prefijo `usuario_id` de la consulta de roles, que devuelve pocas filas por usuario.
- Los helpers de propiedad navegan claves primarias (`vehiculo.id`, `orden_trabajo.id`, `cliente.id`) y `cliente.usuario_id`, que ya tiene el índice único parcial `uq_cliente_usuario`.
- No hay columnas, constraints ni triggers nuevos. La verificación de implementación es `alembic check` (o `alembic revision --autogenerate` en seco) sin operaciones pendientes.

**Si durante la implementación apareciera la necesidad de un índice compuesto adicional** (por ejemplo `(usuario_id, revocada_en, vence_en)`): queda fuera de este change, se justifica con medición y se ejecuta como tarea separada con migración revisada a mano (regla dura #8). No se agrega "por las dudas".

### D9: Estrategia de test de las dependencias

**Decisión**:

- **Unitarios puros** (sin HTTP): `get_roles_vigentes` contra `contexto_auth`; `es_duenio_de_vehiculo` / `es_duenio_de_orden` con datos sembrados en la transacción del test; validación de `require_roles("ADMN")` → `ValueError` al construir la dependencia.
- **HTTP sobre la app real** para lo que ya existe: `GET /auth/yo` sin cookie → `401`; con rol revocado → la respuesta deja de listarlo; con `debe_cambiar_password=true` → sigue respondiendo `200` (exento por RN-06).
- **HTTP con router sonda** para lo que todavía no tiene endpoint de dominio: un `APIRouter` definido en el archivo de test, montado con `app.include_router(sonda, dependencies=[Depends(requiere_password_actualizada)])` o con `Depends(require_roles(...))` según el caso, y removido en el `finally` de la fixture. El router sonda **no** es código de producción.
- **Test de cableado**: introspección de `main.router_protegido.dependencies` y de las rutas incluidas para verificar que el gating está efectivamente montado, de modo que el test sonda no sea la única evidencia.

**Rationale**: sin endpoints de dominio no se puede probar `403` de gating ni `require_roles` por HTTP real; la sonda prueba la dependencia real (no una réplica de su lógica), y el test de cableado cubre el riesgo de que `main.py` olvide montarla. La alternativa —adelantar endpoints de dominio— está fuera de alcance.

**Alternativa descartada**: probar `require_roles` sólo con `TestClient` sobre un `FastAPI` nuevo — verifica la dependencia pero no que la app real la monte; se combina con el test de cableado.

## Risks / Trade-offs

- **[Riesgo] Una consulta extra por request protegida** → `get_roles_vigentes` agrega un `SELECT` indexado por `usuario_id`. Mitigación: el índice parcial existente cubre el prefijo; si se vuelve un cuello de botella se memoiza por request (no entre requests) sin cambiar el contrato. Se descarta cachear entre requests porque viola RN-04.
- **[Riesgo] Dos relojes (aplicación vs. base)** → `vence_en` se escribe desde la aplicación (C-12) y se compara con el reloj de la aplicación; `now()` de PostgreSQL no se usa para autorizar. Mitigación: un único origen de tiempo en el proceso; documentado en D2. Un desfase de reloj entre nodos de aplicación se acepta como limitación del TP (sin reloj distribuido, cap. 7 fuera de alcance).
- **[Riesgo] Exención por prefijo `/auth/` demasiado amplia** → cualquier ruta nueva bajo `/auth/` queda exenta del gating de contraseña. Mitigación: `/auth/*` es exactamente el namespace que RN-06 declara exento y sólo debe contener endpoints de ciclo de vida de sesión; la revisión de C-11/C-17 debe respetarlo.
- **[Riesgo] `/auth/logout` en el grupo público** → se aparta de la enumeración literal de CHANGES. Mitigación: se documenta en D5, se cubre con un escenario explícito ("logout sin sesión responde 200") y se marca para confirmación humana en governance ALTO.
- **[Riesgo] Quitar `selectinload(Usuario.asignaciones)` rompe consumidores ocultos** → Mitigación: verificación con `grep -rn "\.asignaciones" app/ tests/` como tarea previa al cambio; los únicos consumidores están en el alcance.
- **[Trade-off] `require_roles` no conoce jerarquías** → `ADMIN` no implica automáticamente `RECEPCION`. Es deliberado: RN-04 habla de roles vigentes, no de herencia, y cada ruta declara explícitamente los roles que acepta (`require_roles("ADMIN", "RECEPCION")`).
- **[Trade-off] Helpers de propiedad devuelven `bool`** → cada endpoint debe convertir `False` en `403` o `404`. Cuesta tres líneas por endpoint, pero permite no filtrar la existencia de recursos ajenos cuando el contrato lo requiera.
- **[Trade-off] Tests de integración dependen de PostgreSQL** → coherente con la regla dura #9 (índices parciales y timestamps son load-bearing). Si PostgreSQL no está disponible, los tests se `skip` con la convención existente del repo.
- **[Riesgo] `main.py` sigue siendo el único punto de montaje** → un router nuevo que se incluya directamente en `app` (en lugar de `router_protegido`) queda sin gating. Mitigación: el test de cableado verifica que `app.routes` no contenga rutas de dominio fuera de los dos grupos; se documenta en AGENTS.md/CHANGES para los changes siguientes.

## Migration Plan

1. **Sin migración de esquema ni configuración**: el deploy es sólo código (nuevas dependencias, dos archivos `repository.py`, separación de routers y montaje en `main.py`).
2. **Orden de despliegue**: desplegar primero el código; no hay consumidores de los helpers de propiedad todavía (C-15/C-16 los usarán). El único cambio observable en producción es `403` en rutas de dominio para usuarios con contraseña pendiente y para roles revocados, que es el comportamiento buscado.
3. **Rollback**: revertir `main.py` al montaje plano y quitar las dependencias nuevas. No hay datos que limpiar ni migraciones que deshacer. Los cambios de `obtener_usuario_actual` (D3) se revierten restaurando el `selectinload`.
4. **Verificación post-deploy**: `GET /health/live` sin cookie → `200`; `GET /auth/yo` sin cookie → `401`; usuario con rol revocado → `403` en su ruta; usuario con contraseña pendiente → `403` en dominio y `200` en `/auth/yo`.

## Notas para la revisión de governance (ALTO)

1. **`/auth/logout` en el grupo público** (D5): se desvía de la enumeración literal de CHANGES para preservar el contrato idempotente de C-09. ¿Se acepta?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — `/auth/logout` se mantiene en `router_publico` para preservar el `200` idempotente de C-09.
2. **Exención del gating por prefijo de path** (D5): ¿se prefiere una lista explícita de rutas exentas, con el costo de tener que actualizarla en C-11?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — se acepta la exención por prefijo `/auth/` y `/health/`.
3. **Propiedad de orden sólo por vehículo** (D6): se asume que `mecanico_id` no otorga propiedad según RN-17. ¿Correcto, o C-16 espera que el mecánico asignado también pase `es_duenio_de_orden`?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — `mecanico_id` no otorga propiedad; RN-17 es regla CLIENTE. Si C-16 necesita acceso por asignación de mecánico, se agrega un helper separado y nunca se amplía `es_duenio_de_orden`.
4. **Vehículos con `borrado_en`** (D6): la propiedad no filtra bajas lógicas. ¿Se acepta que el cliente siga viendo órdenes históricas de un vehículo dado de baja?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — la propiedad ignora `borrado_en` para que el cliente conserve acceso al historial.
