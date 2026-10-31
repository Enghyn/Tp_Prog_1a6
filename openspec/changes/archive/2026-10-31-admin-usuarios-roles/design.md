# Design

## Context

Ver `proposal.md` — Why. Estado relevante del repositorio al iniciar este change:

- `app/modules/usuarios/` ya contiene `models.py`, `schemas.py`, `repository.py`, `service.py` y `router.py` (con `router_publico` y `router_autenticado`, ambos con prefijo `/auth`).
- `app/core/dependencies.py` expone `SesionActual`, `obtener_usuario_actual`, `get_roles_vigentes` y la fábrica `require_roles(*roles)`. **No existe** un `require_admin`; la fábrica es la única puerta. `require_roles` relee `asignacion_rol` en cada petición (RN-04) y devuelve `SesionActual`, por lo que sirve tanto de guarda como de fuente del `id` del administrador.
- `main.py` monta sólo dos sub-routers: `health.router` y `usuarios_router.router_publico` en `router_publico`; `usuarios_router.router_autenticado` en `router_protegido` (que aplica `requiere_password_actualizada`).
- `app/core/paginacion.py` expone `ParametrosPagina`/`Pagina` (campos en español) y los envoltorios `PageParams`/`Page` (entrada/salida en inglés). Ningún router los usa todavía; sólo hay tests.
- `app/core/errors.py`: `NoEncontradoError` (404), `ConflictoError` (409), `ReglaNegocioError` (422), `ProhibidoError` (403), `NoAutenticadoError` (401). `main.py` mapea `IntegrityError` a `409 CONFLICTO_INTEGRIDAD`.
- `app/core/seguridad.py`: `hash_password(contrasena, app_state)` ejecuta bcrypt en `asyncio.to_thread` acotado por `app.state.bcrypt_semaforo`.
- `repository.py` ya tiene `obtener_sesion_auditoria` (sesión propia + `async with .begin()`), `registrar_evento`, `buscar_usuario_por_email` y `obtener_roles_vigentes_por_usuario`.
- `service.py` ya tiene `auditar_acceso(sesion_auditoria, RegistroAcceso(...))`, patrón que escribe `evento_seguridad` y, opcionalmente, `intento_acceso`.
- **No existe** `UnitOfWork` (C-14 pendiente). C-11 dejó el patrón: sesión dedicada por dependencia + `async with sesion.begin():` + `TODO(C-14)`.
- Restricciones que mandan: reglas duras #1 (nunca `HTTPException` ad-hoc), #2 (sin `commit()` en handlers ni repositorios; el único `commit` es el `__aexit__` del `async with ... begin()`), #3 (`lazy="raise"` y `selectinload` explícito), #4 (los roles del token no autorizan), #6 (`async def`), #9 (tests contra PostgreSQL real), #15 (`test/` sólo `.http`/`.sql`).

## Goals / Non-Goals

**Goals:**

- Añadir la superficie administrativa de personal y roles sin cambiar los contratos existentes de `/auth/*`.
- Dejar la autorización de esas rutas apoyada **exclusivamente** en `require_roles("ADMIN")` (una sola fuente de verdad para el 403).
- Implementar RN-03 (una asignación abierta por rol), RN-05 (autoprotección) y el historial íntegro de asignaciones con revocación lógica.
- Exponer `evento_seguridad` con paginación y filtros usando los helpers de `app/core/paginacion.py`, sin agregar esquema.
- Mantener el nivel de deuda transaccional que dejó C-11, sin adelantar C-13/C-14.

**Non-Goals:**

- Listado, baja lógica (`activo`) y borrado de usuarios; reset de contraseña por un tercero.
- Jerarquía de repositorios y `UnitOfWork` (C-13/C-14): aquí sólo la sesión dedicada y el `TODO(C-14)`.
- Bloqueos pesimistas u optimistas sobre `asignacion_rol` (capítulo 7, fuera de alcance del TP).
- Índice sobre `evento_seguridad` y cualquier migración.
- Alta de clientes/vehículos y todo lo de C-15 en adelante.

## Decisions

### D1: Ubicación de los routers y guarda de ADMIN

**Decisión**: extender `app/modules/usuarios/router.py` (no crear módulos ni archivos nuevos, para respetar la estructura obligatoria de `app/modules/<módulo>/router.py` de KB 02) con dos routers:

```python
solo_admin = require_roles("ADMIN")  # una sola instancia por proceso

router_admin_usuarios = APIRouter(
    prefix="/usuarios",
    tags=["Administración de usuarios"],
    dependencies=[Depends(solo_admin)],
)
router_admin_eventos = APIRouter(
    prefix="/eventos",
    tags=["Auditoría"],
    dependencies=[Depends(solo_admin)],
)
```

`main.py` los monta en `router_protegido`, de modo que heredan `requiere_password_actualizada` (RN-06) y quedan fuera de las exenciones por prefijo `/auth/` y `/health/`. Los handlers que necesitan el `id` del administrador declaran `sesion_actual: Annotated[SesionActual, Depends(solo_admin)]`.

**Rationale**: `solo_admin` se construye **una vez**: FastAPI cachea dependencias por identidad del callable, así que la guarda de router y el parámetro del handler comparten la misma ejecución y una sola consulta a `asignacion_rol` por petición. Definir `require_roles("ADMIN")` dos veces crearía dos callables distintos y duplicaría la consulta.

**Alternativa descartada**: un `require_admin` nuevo en `app/core/dependencies.py`. Se descarta porque `require_roles` ya devuelve `SesionActual` y agregar un alias en `core/` amplía la superficie pública sin necesidad; C-15/C-16 pueden definir su propio alias si lo necesitan.

**Alternativa descartada**: archivo `router_admin.py` separado. Se descarta para no desviarse de la estructura obligatoria (KB 02 enumera `router.py` por módulo) y porque la auditoría de eventos vive en la misma tabla/módulo que `evento_seguridad`.

### D2: Transacciones sin UnitOfWork

**Decisión**: nueva dependencia `obtener_sesion_admin_usuarios(request)` en `repository.py`, gemela de `obtener_sesion_cambio_password`, que entrega una sesión dedicada a las escrituras de dominio (alta, asignación, revocación). El servicio envuelve **una** escritura de dominio en `async with sesion_admin.begin():` con un comentario `# TODO(C-14): reemplazar este límite transaccional local por UnitOfWork.__aexit__.` La auditoría se escribe **después** del commit de dominio, con `obtener_sesion_auditoria` + `auditar_acceso` (transacción independiente, igual que C-09/C-11).

**Rationale**: la sesión de `get_session` ya tiene una transacción implícita abierta por las consultas de autorización (`require_roles`), por lo que `sesion.begin()` sobre ella fallaría. El patrón de sesión dedicada es el que ya demostró funcionar en C-11 y aísla el bloque de escritura del ciclo de vida de la request.

**Consecuencia asumida**: si la escritura de auditoría falla, la operación de dominio ya está confirmada. Es la misma deuda aceptada en C-11 y queda resuelta cuando C-14 introduzca el UoW por request. Los tests fijan la parte observable (evento presente tras el éxito) y no el orden de commits.

**Consecuencia para los tests**: `tests/conftest.py::contexto_auth` debe overridear también `obtener_sesion_admin_usuarios`; si no, las rutas nuevas escaparían de la transacción externa del fixture y romperían el aislamiento.

### D3: Contrato de alta de personal

**Decisión**:

```python
class SolicitudAltaUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr            # normalizado a strip+lower, igual que SolicitudLogin
    nombre: str                # min_length=1, max_length=120, strip
    password: str              # min_length=8, max_length=72

class UsuarioCreado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool
```

`POST /usuarios` responde `201` con `response_model=UsuarioCreado`. La contraseña se hashea con `await hash_password(password, request.app.state)` (semáforo de `lifespan`); **nunca** `hash_password_sync`. El usuario se crea con `activo=True` y `debe_cambiar_password=True`, sin asignaciones de rol.

**Rationale**: `UsuarioPublico` (existente) no incluye `activo`; reutilizarlo obligaría a cambiar un contrato de `/auth/*`. Un schema propio mantiene `UsuarioPublico` intacto.

**Alternativa descartada**: extender `UsuarioPublico` con `activo` para reutilizarlo. Se descarta por el riesgo de alterar la serialización de `/auth/login` y `/auth/yo`.

### D4: Detección de email duplicado sin depender del nombre de la constraint

**Decisión**: pre-chequeo con `buscar_usuario_por_email(sesion, email_normalizado)` → `ConflictoError("El email ya está registrado", "EMAIL_DUPLICADO")`. El `IntegrityError` de `uq/ix` sobre `usuario.email` queda sólo como red de seguridad y lo traduce el handler global a `409 CONFLICTO_INTEGRIDAD`.

**Rationale**: el repo arrastra drift conocido entre `usuario_email_key` (constraint en la migración) e `ix_usuario_email` (metadata); cualquier lógica que parsee el mensaje de la constraint es frágil. El pre-chequeo da el `codigo` de dominio y el handler global garantiza que nunca se filtre el nombre de la constraint (RN-18).

**Trade-off**: entre el `SELECT` y el `INSERT` hay una ventana de carrera; la resuelve el índice único (409 genérico). Aceptado.

### D5: Respuesta del historial de roles

**Decisión**:

```python
class AsignacionRolPublica(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    rol: str
    desde: datetime
    vence_en: datetime | None
    revocada_en: datetime | None
    otorgada_por: int | None
    vigente: bool

class HistorialRoles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: int
    asignaciones: list[AsignacionRolPublica]
```

`vigente` se calcula en el servicio con el mismo predicado de `obtener_roles_vigentes_por_usuario` (`revocada_en IS NULL` y `vence_en` nulo o futuro) evaluado con un único `ahora` por request. Orden: `desde DESC, id DESC`.

**Rationale**: la KB pide "historial (vigentes y revocadas)" y el cliente necesita distinguir una asignación vencida de una revocada sin reimplementar la regla de vigencia. Devolver `otorgada_por` como `id` evita un join a `usuario` y un N+1.

**Alternativa descartada**: dos listas (`vigentes`/`revocadas`). Se descarta porque una asignación vencida pero no revocada no cae limpiamente en ninguna de las dos.

### D6: Flujo de asignación de rol

**Decisión**: en `service.asignar_rol`, dentro de una única transacción de dominio:

1. Verificar que el usuario existe (`sesion_admin.get(Usuario, usuario_id)`) → si no, `NoEncontradoError(..., "USUARIO_NO_ENCONTRADO")`.
2. Buscar la asignación abierta `(usuario_id, rol)` con `revocada_en IS NULL`.
3. Si existe y está **vigente** (`vence_en` nulo o `> ahora`) → `ConflictoError("El usuario ya tiene ese rol vigente", "ROL_YA_ASIGNADO")` (RN-03, detectado antes del `INSERT` para dar mensaje de dominio).
4. Si existe y está **vencida** → `UPDATE ... SET revocada_en = ahora` (cierra la fila, preserva historial).
5. `INSERT` con `desde = ahora`, `vence_en` de la solicitud, `revocada_en = NULL`, `otorgada_por = sesion_actual.usuario.id`; `flush()`.
6. Commit del bloque, luego `auditar_acceso(..., accion="ROL_ASIGNADO")`.
7. Responder `201` con `AsignacionRolPublica` (`vigente=True`).

**Rationale**: el índice único parcial `uq_asignacion_rol_abierta` sólo cubre `revocada_en IS NULL`, es decir una asignación **vencida** sigue ocupando el índice. Sin el paso 4, "reasignar un rol vencido" fallaría con `409 CONFLICTO_INTEGRIDAD` en vez de abrir la fila nueva que pide la KB 03.

**Nota de validación**: el schema usa `rol: Literal["ADMIN", "RECEPCION", "MECANICO", "CLIENTE"]` (422 `ERROR_VALIDACION` automático, espejo del CHECK de la base) y un `field_validator` que exige `vence_en` con zona horaria y estrictamente futuro (422 `ERROR_VALIDACION`).

### D7: Flujo de revocación y autoprotección (RN-05)

**Decisión**: orden estricto de comprobaciones en `service.revocar_rol`:

1. Usuario inexistente → `404 USUARIO_NO_ENCONTRADO`.
2. Sin asignación abierta **vigente** para ese `rol` → `404 ASIGNACION_NO_ENCONTRADA` (una fila vencida con `revocada_en` nulo no es revocable: ya no está vigente).
3. `rol == "ADMIN"` y `usuario_id == sesion_actual.usuario.id` → `409 AUTOPROTECCION_ADMIN`.
4. `rol == "ADMIN"` y `contar_admins_vigentes(sesion) <= 1` → `409 ULTIMO_ADMIN`, con el mismo predicado de vigencia (`revocada_en IS NULL AND (vence_en IS NULL OR vence_en > :ahora)`).
5. `UPDATE asignacion_rol SET revocada_en = ahora` sobre la fila; `flush()`; commit; `auditar_acceso(..., accion="ROL_REVOCADO")`; responder `200`.

La comprobación 3 va **antes** de la 4 porque, en el caso "soy el único admin", la respuesta correcta es la de autoprotección, no la de último admin.

**Rationale**: RN-05 son dos garantías distintas y el orden de los códigos es observable. El conteo se hace dentro de la transacción de dominio (no en la de auditoría) para que la decisión y la escritura compartan el estado.

**Trade-off**: sin `SELECT ... FOR UPDATE`, dos administradores podrían revocar simultáneamente los dos últimos `ADMIN`. El capítulo 7 está fuera de alcance y `knowledge-base/10_preguntas_abiertas.md` ya documenta la limitación; se registra en Riesgos. RN-03 sí queda blindada por el índice único parcial.

### D8: Consulta paginada de eventos

**Decisión**: `GET /eventos` acepta `page`/`size` vía `PageParams` (defaults 1/10, `size` 1..100) más `actor: str | None`, `desde: datetime | None`, `hasta: datetime | None`. La consulta se construye así:

```python
filtros = []
if actor is not None:  filtros.append(EventoSeguridad.actor == actor)
if desde is not None:  filtros.append(EventoSeguridad.cuando >= desde)
if hasta is not None:  filtros.append(EventoSeguridad.cuando <= hasta)

total = await sesion.scalar(select(func.count()).select_from(EventoSeguridad).where(*filtros))
filas = (await sesion.execute(
    select(EventoSeguridad).where(*filtros)
    .order_by(EventoSeguridad.cuando.desc(), EventoSeguridad.id.desc())
    .offset((page - 1) * size).limit(size)
)).scalars().all()
return Page(items=[EventoPublico.model_validate(f) for f in filas], total=total, page=page, size=size)
```

`response_model=Page[EventoPublico]` con `EventoPublico = {id, cuando, actor, accion}`.

**Rationale**: `id DESC` como desempate da orden total y estable aunque dos eventos compartan `cuando` (los triggers escriben con `now()` y pueden colisionar en el mismo instante). El filtro `actor` es igualdad estricta (decisión del usuario) para que sea predecible y compatible con un índice futuro.

**Nota sobre `Page`**: `Page.model_dump` reescribe `pagina`/`tamanio` a `page`/`size`; construir siempre con `Page(items=..., total=..., page=..., size=...)` y no con los nombres en español.

**Validación del rango**: `desde > hasta` se detecta en el handler y se reporta con `ReglaNegocioError("Rango de fechas inválido", "RANGO_FECHAS_INVALIDO")` → `422`, respetando la regla dura #1 (nunca `HTTPException` ad-hoc). Fechas sin zona horaria o con formato inválido las rechaza Pydantic (`AfterValidator`) con `422 ERROR_VALIDACION`.

### D9: Eventos de auditoría nuevos

**Decisión**: reutilizar `auditar_acceso`/`RegistroAcceso` sin agregar funciones de escritura:

| Operación | `accion` | `actor` | `exito` |
|---|---|---|---|
| `POST /usuarios` | `USUARIO_CREADO` | email del admin | `None` (no toca `intento_acceso`) |
| `POST /usuarios/{id}/roles` | `ROL_ASIGNADO` | email del admin | `None` |
| `DELETE /usuarios/{id}/roles/{rol}` | `ROL_REVOCADO` | email del admin | `None` |

`ip` se toma de `request.client.host` con fallback `"desconocida"`, igual que en `login`/`cambiar_password`. `cuando` es el mismo instante que se usó para `desde`/`revocada_en`.

**Rationale**: el actor de `evento_seguridad` es texto libre; usar el email del administrador lo hace consultable con `GET /eventos?actor=<email>` sin agregar columnas. `exito=None` evita contaminar `intento_acceso` con eventos que no son intentos de login.

### D10: Códigos de error

**Decisión**:

| Situación | Excepción | HTTP | `codigo` |
|---|---|---|---|
| Sin cookie / token inválido / expirado / `iat` viejo | `NoAutenticadoError` (existente) | 401 | `CREDENCIALES_INVALIDAS` |
| Autenticado sin `ADMIN` vigente | `ProhibidoError` (vía `require_roles`) | 403 | `PERMISOS_INSUFICIENTES` |
| Contraseña provisoria pendiente | `ProhibidoError` (vía `requiere_password_actualizada`) | 403 | `CAMBIO_PASSWORD_REQUERIDO` |
| Usuario inexistente | `NoEncontradoError` | 404 | `USUARIO_NO_ENCONTRADO` |
| Asignación no vigente a revocar | `NoEncontradoError` | 404 | `ASIGNACION_NO_ENCONTRADA` |
| Email duplicado (pre-chequeo) | `ConflictoError` | 409 | `EMAIL_DUPLICADO` |
| Rol ya vigente (RN-03) | `ConflictoError` | 409 | `ROL_YA_ASIGNADO` |
| Revocar el propio `ADMIN` (RN-05) | `ConflictoError` | 409 | `AUTOPROTECCION_ADMIN` |
| Dejar el sistema sin `ADMIN` (RN-05) | `ConflictoError` | 409 | `ULTIMO_ADMIN` |
| Email/rol/vencimiento/campos inválidos | `RequestValidationError` | 422 | `ERROR_VALIDACION` |
| `desde > hasta` | `ReglaNegocioError` | 422 | `RANGO_FECHAS_INVALIDO` |
| Carrera perdida en el alta o la asignación | handler global de `IntegrityError` | 409 | `CONFLICTO_INTEGRIDAD` |

## Risks / Trade-offs

- **Sin índice en `evento_seguridad`** → `GET /eventos` hace `seq scan` más un `COUNT(*)` completo; el costo crece linealmente con la auditoría acumulada. Mitigación: aceptado por decisión del usuario, documentado aquí y en `knowledge-base/10_preguntas_abiertas.md` como candidato a un change futuro (índice `(cuando DESC, id DESC)` y, si aparece búsqueda por actor, `(actor, cuando)`).
- **Carrera en RN-05** con dos administradores revocando a la vez → Mitigación: limitación documentada del capítulo 7; el escenario no se testea bajo concurrencia real, sólo secuencialmente.
- **Deuda transaccional (dominio y auditoría en transacciones separadas)** → Mitigación: `TODO(C-14)` explícito junto al `async with ... begin()`; C-14 lo resuelve sin cambiar contratos HTTP.
- **`Page.model_dump` reescribe campos** → Mitigación: construir con `page`/`size` y un test HTTP que verifique el JSON real (`page`, `size`, `total`, `items`), no el `model_dump` aislado.
- **`contexto_auth` sin override de la sesión nueva** rompería el aislamiento de los tests → Mitigación: extender el fixture en la primera tarea del plan y verificar con un test que la escritura no sobrevive al rollback.
- **`IntegrityError` de `usuario.email` con nombres de constraint inconsistentes** → Mitigación: D4 (pre-chequeo + handler global genérico), ningún parseo del mensaje.
- **`lazy="raise"` en `AsignacionRol.usuario`/`otorgado_por_usuario`** → Mitigación: el historial se lee con una consulta plana sobre `asignacion_rol` sin navegar relaciones; no se usa `selectinload` porque no se devuelve el agregado `Usuario`.
- **Regresión en el wiring de C-10** al agregar sub-routers a `router_protegido` → Mitigación: correr la suite completa (`test_autorizacion_rbac.py` incluido) y el conteo de rutas de OpenAPI como verificación de cierre.

## Migration Plan

1. Sin migración: las tablas `usuario`, `asignacion_rol` y `evento_seguridad` ya existen en `001_auth_core` con sus CHECK e índices.
2. Despliegue: agregar los dos routers a `router_protegido` en `main.py`; no hay pasos de datos ni backfill (los usuarios del seed ya tienen sus asignaciones).
3. Rollback: quitar los `include_router` de `main.py`; no hay estado persistido que deshacer más allá de las filas creadas por el propio uso de la API (todas con historial, ninguna borrada).
4. `alembic check` sigue fallando por el drift preexistente documentado en `2026-10-30-rbac-route-groups`; no forma parte de la verificación de este change.

## Notas para la revisión de governance (ALTO)

1. **`GET /eventos` con coincidencia exacta de actor** (D8): ¿se acepta que `?actor=admin` no encuentre a `admin@taller.local`?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — igualdad estricta.
2. **Sin migración en C-12** (Riesgos): ¿se acepta el `seq scan` sobre `evento_seguridad` como limitación diferida?
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — sin índice ni migración en este change.
3. **`POST /usuarios` sin roles en el cuerpo** (D3): el alta y la asignación quedan en dos peticiones.
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — sólo alta de usuario; los roles se asignan por `POST /usuarios/{id}/roles`.
4. **Auditoría en transacción separada del dominio** (D2): se conserva la deuda de C-11 porque C-14 aún no existe.
   **Resolución**: `Aprobado por el usuario (2026-10-31)` — se mantiene el patrón con `TODO(C-14)`; no se adelanta el UoW.
