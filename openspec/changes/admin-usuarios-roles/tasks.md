# Tasks

> **Estado**: planificación únicamente. Ninguna de estas tareas está implementada todavía.
> **Metodología**: Strict TDD en cada unidad de comportamiento: **Rojo** (test que falla por la razón correcta) → **Verde** (implementación mínima) → **Triangular** (casos que obligan a generalizar) → **Refactor** (sin cambiar comportamiento, suite verde). Ningún task de implementación sin su test previo.
> **Reglas duras aplicables**: #1 (`AppError`, nunca `HTTPException` ad-hoc), #2 (sin `commit()` en handlers ni repositorios), #3 (`lazy="raise"`; no navegar relaciones sin precarga), #4 (los roles del token no autorizan), #6 (`async def`), #9 (tests contra PostgreSQL real, nunca SQLite), #13 (type hints + `snake_case`), #15 (`test/` sólo `.http`/`.sql`).
> **Leer antes**: `knowledge-base/03_actores_y_roles.md` §Gestión de Roles y Autenticación, `knowledge-base/06_funcionalidades.md` §3, `knowledge-base/05_reglas_de_negocio.md` §RN-03/§RN-05, `knowledge-base/04_modelo_de_datos.md` §Tablas 1, 2 y 4.

## 1. Safety net y preparación

- [ ] 1.1 Ejecutar `pytest` completo y registrar la línea base en el resumen del change: cantidad de `passed`, `failed` y `skipped`. Si hay fallos preexistentes, se reportan como tales y **no** se corrigen en este change. Verificación: la línea base queda anotada en `tasks.md`.
- [ ] 1.2 Releer `tests/conftest.py::contexto_auth` y `tests/test_autorizacion_rbac.py` para confirmar qué dependencias se overridean y qué aserciones de wiring existen hoy. Verificación: lista de dependencias overrideadas (`get_session`, `obtener_sesion_auditoria`, `obtener_sesion_cambio_password`) anotada; se identifica que `obtener_sesion_admin_usuarios` deberá agregarse en 2.2.
- [ ] 1.3 Verificar que no hace falta migración: `usuario`, `asignacion_rol` (con `uq_asignacion_rol_abierta` y `ck_asignacion_rol_valido`) y `evento_seguridad` existen en `migrations/versions/001_auth_core.py`. Verificación: no se agrega ningún archivo en `migrations/versions/` y `alembic check` sigue fallando por el drift preexistente (documentado, no es regresión de este change).

## 2. Sesión de dominio, routers y guarda de ADMIN

- [ ] 2.1 **Rojo**: en `tests/test_admin_usuarios_sesion.py`, test que usa `obtener_sesion_admin_usuarios` como dependencia inyectada, escribe un `Usuario` y verifica que tras el rollback del fixture la fila no existe. El test debe fallar por `ImportError`. Verificación: falla con `ImportError`, no con un error de base.
- [ ] 2.2 **Verde**: implementar `obtener_sesion_admin_usuarios(request)` en `app/modules/usuarios/repository.py` copiando el patrón de `obtener_sesion_cambio_password` (`getattr(request.app.state, "session_maker", None) or session_maker`) y agregar el override correspondiente en `tests/conftest.py::contexto_auth`. Verificación: 2.1 pasa (green) y ningún test existente de auth se rompe.
- [ ] 2.3 **Rojo**: en `tests/test_admin_usuarios_rutas.py`, test que inspecciona las rutas registradas y afirma los cinco endpoints (`POST /usuarios`, `GET /usuarios/{id}/roles`, `POST /usuarios/{id}/roles`, `DELETE /usuarios/{id}/roles/{rol}`, `GET /eventos`), y que sin cookie responden `401 CREDENCIALES_INVALIDAS`. Verificación: falla porque las rutas no existen.
- [ ] 2.4 **Verde**: en `app/modules/usuarios/router.py` definir `solo_admin = require_roles("ADMIN")` (una sola instancia), los routers `router_admin_usuarios` (`prefix="/usuarios"`) y `router_admin_eventos` (`prefix="/eventos"`), ambos con `dependencies=[Depends(solo_admin)]`, con handlers mínimos que sólo declaren `sesion_actual: Annotated[SesionActual, Depends(solo_admin)]`; montar ambos en `router_protegido` desde `main.py`. Verificación: 2.3 pasa.
- [ ] 2.5 **Triangular (403)**: tests para (a) usuario autenticado sólo con `MECANICO` → `403 PERMISOS_INSUFICIENTES`, (b) ADMIN revocado después de emitir el token (mismo token con claim `ADMIN`) → `403`, (c) ADMIN con `debe_cambiar_password=True` → `403 CAMBIO_PASSWORD_REQUERIDO`. Verificación: los tres pasan y `solo_admin` se evalúa una sola vez por petición (una sola consulta a `asignacion_rol`; se comprueba con un contador de queries o con dos peticiones y `echo` desactivado).
- [ ] 2.6 **Refactor**: extraer el helper de tests que emite cookie de ADMIN (`_cliente_admin`/`_token_para`) a `tests/conftest.py` si se repite en 3+ archivos. Verificación: la suite sigue verde.

## 3. Alta de personal (`POST /usuarios`)

- [ ] 3.1 **Rojo**: `tests/test_admin_alta_usuario.py` — test de alta exitosa: `201`, `id` presente, `email` normalizado a minúsculas, `activo=True`, `debe_cambiar_password=True`, y el `password_hash` almacenado no es igual al texto enviado pero `verify_password_async` lo valida. Verificación: falla por ruta/servicio inexistente.
- [ ] 3.2 **Verde**: `SolicitudAltaUsuario` y `UsuarioCreado` en `schemas.py` (D3, `extra="forbid"`, `EmailStr` con normalización `strip+lower`, `nombre` 1..120, `password` 8..72 con `validar_complejidad_password`), `crear_usuario(...)` en `repository.py` (`flush()`, **sin** `commit()`) y `dar_de_alta_usuario(...)` en `service.py` usando `await hash_password(password, app_state)`. Handler con `status_code=201`, `response_model=UsuarioCreado`. Verificación: 3.1 pasa.
- [ ] 3.3 **Triangular (no filtrar la contraseña)**: test que afirma que el cuerpo del `201` no contiene `password`, `password_hash` ni `$2b$`. Verificación: pasa sin cambiar producción.
- [ ] 3.4 **Triangular (409)**: test de email duplicado con distinta capitalización → `409 EMAIL_DUPLICADO`, cantidad de usuarios con ese email sigue siendo 1, y **no** se crea evento `USUARIO_CREADO`. Implementar el pre-chequeo con `buscar_usuario_por_email` (D4).
- [ ] 3.5 **Triangular (409 no revela esquema)**: test que afirma que el cuerpo del `409` no contiene `usuario_email_key`, `ix_usuario_email` ni `INSERT`. Verificación: pasa con el handler global actual.
- [ ] 3.6 **Triangular (422)**: tests parametrizados de campo extra (`activo`), email inválido (`nuevo-taller.local`), contraseña de 7 caracteres, contraseña sin dígito, contraseña sin mayúscula y `nombre` vacío; en todos se verifica `422 ERROR_VALIDACION`, `detail[].loc` correcto y que no se creó usuario.
- [ ] 3.7 **Triangular (la validación no repite secretos)**: test que afirma que el cuerpo del `422` por contraseña inválida no contiene el valor de `password` ni la contraseña enviada.
- [ ] 3.8 **Triangular (login con la provisoria)**: test `POST /auth/login` con el usuario recién creado → `200`, `debe_cambiar_password=True`, `roles=[]`.
- [ ] 3.9 **Refactor**: unificar la normalización de email entre `SolicitudLogin` y `SolicitudAltaUsuario` en una función compartida de `schemas.py`. Verificación: suite verde.

## 4. Historial de roles (`GET /usuarios/{id}/roles`)

- [ ] 4.1 **Rojo**: `tests/test_admin_historial_roles.py` — usuario con `MECANICO` revocado y `RECEPCION` vigente → `200` con dos asignaciones ordenadas por `desde` descendente, `revocada_en` correcto y sólo una con `vigente=True`. Verificación: falla por endpoint inexistente.
- [ ] 4.2 **Verde**: `AsignacionRolPublica`/`HistorialRoles` (D5), `listar_asignaciones(sesion, usuario_id)` en `repository.py` (`ORDER BY desde DESC, id DESC`, sin navegar relaciones por `lazy="raise"`) y `obtener_historial_roles(...)` en `service.py` que calcula `vigente` con un único `ahora`. Verificación: 4.1 pasa.
- [ ] 4.3 **Triangular**: (a) asignación con `vence_en` en el pasado y `revocada_en=None` → `vigente=False`; (b) usuario sin asignaciones → `200` con lista vacía; (c) usuario inexistente → `404 USUARIO_NO_ENCONTRADO`. Verificación: los tres pasan.
- [ ] 4.4 **Refactor**: extraer el predicado de vigencia a un helper reutilizado por historial, asignación y conteo de administradores. Verificación: suite verde y ningún cambio de comportamiento.

## 5. Asignación de rol (`POST /usuarios/{id}/roles`)

- [ ] 5.1 **Rojo**: `tests/test_admin_asignacion_rol.py` — `201` con `rol`, `vence_en=None`, `revocada_en=None`, `otorgada_por` igual al `id` del admin autenticado y `vigente=True`. Verificación: falla por endpoint inexistente.
- [ ] 5.2 **Verde**: `SolicitudAsignacionRol` (`rol: Literal[...]`, `vence_en` opcional con `AfterValidator` de zona horaria y futuro, `extra="forbid"`) y `asignar_rol(...)` en `service.py` con el flujo de D6 (verificación de usuario, cierre de vencida, `INSERT`, `flush()`, **sin** `commit()` en el repositorio). Handler `status_code=201`. Verificación: 5.1 pasa.
- [ ] 5.3 **Triangular (vencimiento futuro)**: test con `vence_en` futuro con offset no UTC → la respuesta devuelve exactamente el instante enviado (sin truncar fracciones ni convertir a UTC sin offset). Verificación: pasa.
- [ ] 5.4 **Triangular (efecto en autorización)**: test sobre una sonda que exige `RECEPCION` (patrón `montar_sonda` de `tests/test_autorizacion_rbac.py`) — antes `403`, tras la asignación `200` con el mismo token. Verificación: pasa.
- [ ] 5.5 **Triangular (404)**: asignar rol a `id` inexistente → `404 USUARIO_NO_ENCONTRADO` y ninguna fila creada.
- [ ] 5.6 **Triangular (409 RN-03)**: doble asignación vigente → `409 ROL_YA_ASIGNADO`, una sola fila abierta y `desde`/`vence_en` originales intactos. Verificación: pasa.
- [ ] 5.7 **Triangular (reasignación de vencido)**: asignación previa con `vence_en` pasado y `revocada_en=None` → `201`, fila anterior con `revocada_en` no nulo y segunda fila abierta; el historial muestra ambas. Verificación: pasa (demuestra que el cronológico cierra la vencida antes del `INSERT`, evitando el choque con `uq_asignacion_rol_abierta`).
- [ ] 5.8 **Triangular (422)**: `{"rol": "GERENTE"}` → `422 ERROR_VALIDACION`; `vence_en` pasado → `422 ERROR_VALIDACION`; campo extra `otorgada_por` → `422`. En los tres, ninguna fila creada.
- [ ] 5.9 **Refactor**: mover el cálculo de `ahora` y la construcción de `AsignacionRol` a una función única usada por asignación y reasignación. Verificación: suite verde.

## 6. Revocación y autoprotección (`DELETE /usuarios/{id}/roles/{rol}`)

- [ ] 6.1 **Rojo**: `tests/test_admin_revocacion_rol.py` — revocación exitosa: `200`, la fila conserva su `desde` y queda con `revocada_en` no nulo, la cantidad total de filas de `asignacion_rol` no disminuye. Verificación: falla por endpoint inexistente.
- [ ] 6.2 **Verde**: `revocar_rol(...)` en `service.py` con el flujo de D7 (pasos 1, 2, 5) y `RespuestaRevocacionRol` en `schemas.py`. Verificación: 6.1 pasa.
- [ ] 6.3 **Triangular (efecto inmediato)**: con sonda que exige `RECEPCION`, tras la revocación la misma petición con el mismo token responde `403 PERMISOS_INSUFICIENTES`.
- [ ] 6.4 **Triangular (404)**: (a) rol que el usuario nunca tuvo, (b) rol con asignación ya revocada, (c) rol con asignación vencida (`vence_en` pasado, `revocada_en=None`), (d) usuario inexistente → `404 ASIGNACION_NO_ENCONTRADA` en (a)-(c) y `404 USUARIO_NO_ENCONTRADO` en (d); en todos, ninguna fila modificada.
- [ ] 6.5 **Triangular (422)**: `DELETE /usuarios/{id}/roles/GERENTE` → `422 ERROR_VALIDACION`.
- [ ] 6.6 **Triangular (409 autoprotección)**: admin revoca su propio `ADMIN` → `409 AUTOPROTECCION_ADMIN`, asignación vigente intacta. Test adicional: admin con `ADMIN` y `MECANICO` revoca su propio `MECANICO` → `200` y su `ADMIN` no cambia.
- [ ] 6.7 **Triangular (409 último admin)**: (a) único `ADMIN` vigente en el sistema, revocado por otro admin → `409 ULTIMO_ADMIN` y asignación intacta; (b) el segundo `ADMIN` del sistema está vencido → `409 ULTIMO_ADMIN`; (c) con dos `ADMIN` vigentes la revocación procede y queda exactamente uno. Verificación: los tres pasan.
- [ ] 6.8 **Triangular (orden de códigos)**: admin que es el único `ADMIN` vigente intenta revocar su propio `ADMIN` → `409 AUTOPROTECCION_ADMIN` (no `ULTIMO_ADMIN`).
- [ ] 6.9 **Refactor**: unificar la consulta de conteo de administradores vigentes con la usada por `require_roles` (mismo predicado, sin duplicar SQL). Verificación: suite verde.

## 7. Eventos de auditoría de las operaciones

- [ ] 7.1 **Rojo**: `tests/test_admin_auditoria_operaciones.py` — test parametrizado por operación (`alta` → `USUARIO_CREADO`, `asignación` → `ROL_ASIGNADO`, `revocación` → `ROL_REVOCADO`) que verifica la existencia de un evento con `actor` igual al email del admin y `cuando` no nulo. Verificación: falla porque no se escribe ningún evento nuevo.
- [ ] 7.2 **Verde**: llamar `auditar_acceso(sesion_auditoria, RegistroAcceso(email=..., ip=request.client.host o "desconocida", actor=admin.email, accion=..., exito=None, cuando=ahora))` después del commit de dominio en los tres servicios (D9). Verificación: 7.1 pasa.
- [ ] 7.3 **Triangular (rechazos sin evento)**: para `403`, `404`, `409` y `422` en las tres operaciones, no se crea evento de éxito. Verificación: el conteo de eventos por `accion` no cambia.
- [ ] 7.4 **Triangular (no contamina intentos)**: tras las tres operaciones, `intento_acceso` no gana filas (porque `exito=None`). Verificación: conteo estable antes/después.
- [ ] 7.5 **Refactor**: si las tres llamadas comparten argumentos, extraer un helper `_auditar_operacion(sesion_auditoria, admin, accion, cuando, request)`. Verificación: suite verde.

## 8. Auditoría consultable (`GET /eventos`)

- [ ] 8.1 **Rojo**: `tests/test_admin_eventos.py` — sin `ADMIN` → `403`; con `ADMIN` y 12 eventos sembrados → `200` con `page=1`, `size=10`, `total=12` y 10 `items` ordenados por `cuando` descendente. Verificación: falla por endpoint inexistente.
- [ ] 8.2 **Verde**: `EventoPublico` en `schemas.py`, `contar_eventos`/`listar_eventos` en `repository.py`, `consultar_eventos(...)` en `service.py` y handler con `response_model=Page[EventoPublico]` construido como `Page(items=..., total=..., page=..., size=...)` (D8). Verificación: 8.1 pasa y el JSON expone `page`/`size` (no `pagina`/`tamanio`).
- [ ] 8.3 **Triangular (orden estable)**: dos eventos con el mismo `cuando` → el de `id` mayor primero, repetido en dos consultas consecutivas. Verificación: pasa.
- [ ] 8.4 **Triangular (paginación)**: `page=2&size=10` con 12 eventos → 2 `items`, los más antiguos, `total=12`; página fuera de rango → `200` con `items=[]` y `total` real; `GET /eventos` repetido no cambia la cantidad de filas de `evento_seguridad`.
- [ ] 8.5 **Triangular (rango temporal)**: eventos en los extremos y en el medio → los tres incluidos (bordes inclusive); sólo `desde`; sólo `hasta`; rango sin coincidencias → `200` con `total=0`; `desde > hasta` → `422 RANGO_FECHAS_INVALIDO`.
- [ ] 8.6 **Triangular (actor)**: `actor=<email>` devuelve sólo los de ese actor; `actor=admin` (coincidencia parcial) → `200` con `items=[]`; `actor=SISTEMA`; combinación de `actor` + `desde` + `hasta`.
- [ ] 8.7 **Triangular (contrato inválido)**: `page=0` → `422`; `size=101` → `422`; `desde` sin zona horaria → `422`; `hasta=ayer` → `422`; en los cuatro, `codigo=ERROR_VALIDACION` y `detail[].loc` señala el parámetro.
- [ ] 8.8 **Refactor**: reutilizar el helper de vigencia/ahora del grupo 4 y eliminar duplicación en la construcción de filtros. Verificación: suite verde.

## 9. Verificación integral y cierre

- [ ] 9.1 Ejecutar la suite completa con `pytest` y comparar contra la línea base de 1.1: mismos `skipped`, cero fallos, sólo altas nuevas de tests. Verificación: pegar el resumen en `## TDD Cycle Evidence`.
- [ ] 9.2 Verificación de reglas duras con búsquedas: `HTTPException` fuera de `app/core/errors.py` → 0 hits; `commit(` en `app/modules/**` y `app/core/repository.py` → 0 hits; `hash_password_sync` en `app/modules/**` → 0 hits; `def ` (sincrónico) en los rutas nuevas → 0 hits. Verificación: los cuatro conteos son cero.
- [ ] 9.3 Revisar `/openapi.json`: los cinco endpoints documentados con `201`/`200` donde corresponde y los `422` de validación. Verificación: los paths aparecen una sola vez y sin duplicados de `operationId`.
- [ ] 9.4 Agregar `test/usuarios-admin.http` (archivo manual, sin Python) con: alta, alta duplicada, historial, asignación, doble asignación, reasignación de vencido, revocación, autoprotección, último admin y consultas de `/eventos` con filtros. Verificación: `tests/test_estructura_artefactos.py` sigue verde (sólo `.http`/`.sql` en `test/`).
- [ ] 9.5 Completar la tabla `## TDD Cycle Evidence` con una fila por grupo (archivo de test, capa, safety net, RED, GREEN, TRIANGULATE, REFACTOR).
- [ ] 9.6 Actualizar `CHANGES.md`: marcar `- **Estado**: `[x]` completado` en `[C-12]`. Verificación: el checkbox refleja el estado real del change.

## Notas de implementación

- `solo_admin` debe existir **una sola vez** en `app/modules/usuarios/router.py`: FastAPI cachea por identidad del callable, así que la guarda de router y el parámetro del handler comparten ejecución y consulta.
- El cierre de una asignación vencida (5.7) es obligatorio antes del `INSERT`; sin él, `uq_asignacion_rol_abierta` rechaza la fila nueva porque el índice parcial no excluye filas vencidas.
- `Page`/`PageParams` usan nombres en inglés en entrada/salida mientras `Pagina`/`ParametrosPagina` los usan en español; construir el resultado con `Page(items=..., total=..., page=..., size=...)`.
- Cualquier escritura de dominio debe pasar por `obtener_sesion_admin_usuarios`; la auditoría, siempre por `obtener_sesion_auditoria`. No mezclar sesiones en el mismo bloque.
- `alembic check` falla por drift preexistente; no se usa como criterio de aceptación de este change.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.x | `tests/test_admin_usuarios_sesion.py` | Integración (DB) | pendiente | pendiente | pendiente | pendiente | pendiente |
| 3.x | `tests/test_admin_alta_usuario.py` | HTTP + DB | pendiente | pendiente | pendiente | pendiente | pendiente |
| 4.x | `tests/test_admin_historial_roles.py` | HTTP + DB | pendiente | pendiente | pendiente | pendiente | pendiente |
| 5.x | `tests/test_admin_asignacion_rol.py` | HTTP + DB | pendiente | pendiente | pendiente | pendiente | pendiente |
| 6.x | `tests/test_admin_revocacion_rol.py` | HTTP + DB | pendiente | pendiente | pendiente | pendiente | pendiente |
| 7.x | `tests/test_admin_auditoria_operaciones.py` | Integración (DB) | pendiente | pendiente | pendiente | pendiente | pendiente |
| 8.x | `tests/test_admin_eventos.py` | HTTP + DB | pendiente | pendiente | pendiente | pendiente | pendiente |

## Workflow follow-up

- Archivar con `/opsx:archive admin-usuarios-roles` cuando 9.1-9.6 estén completos.
- Sólo si el apply descubre un cambio de alcance real (por ejemplo, que `Page` no serializa como se espera y obliga a tocar `app/core/paginacion.py`), actualizar este change con `openspec-update-change` antes de archivarlo.
