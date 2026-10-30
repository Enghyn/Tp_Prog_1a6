# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Taller Mecánico API (TP Programación III — Unidades 1 a 6)**.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

> **Criterio de orden**: los changes siguen el orden de los capítulos 1 a 6 del TP, que coincide con la dependencia técnica real (contratos HTTP → asincronía → persistencia → auth → repositorios/UoW/transacciones).
> **Fuera de alcance** (ver `knowledge-base/10_preguntas_abiertas.md`): capítulo 7 (bloqueos pesimistas/optimistas, actualizaciones perdidas) y capítulo 8 (colas distribuidas con Redis). No hay changes para ellos: el aviso al cliente se resuelve con `BackgroundTasks` (C-04) y la concurrencia avanzada queda documentada como limitación.

---

## Árbol de dependencias

```
C-01 foundation-setup
  │
  ├── C-02 http-contracts-and-errors ──────────────────┐
  │                                                    │
  └── C-03 async-crypto                                │
        ├── C-04 background-notifications              │
        └── (consumido por C-08 y C-09)                │
                                                       ▼
                                              C-05 database-lifecycle
                                                └── C-06 auth-models
                                                      │
                                                      ├── C-07 domain-models
                                                      │     ├── C-08 seed-inicial          ← + C-03
                                                      │     └── C-13 repositories         ← + C-09
                                                      │           └── C-14 unit-of-work
                                                      │                 ├── C-15 clientes-vehiculos
                                                      │                 │     └── C-17 registro-atomico   ← + C-09
                                                      │                 └── C-16 repuestos-stock
                                                      │
                                                      └── C-09 auth-login-jwt               ← + C-03
                                                            ├── C-10 rbac-route-groups
                                                            │     └── C-12 admin-usuarios-roles
                                                            └── C-11 password-lifecycle

C-15 + C-16 ──▶ C-18 ordenes-apertura-consulta
                  └── C-19 ordenes-transiciones     ← + C-04
                        └── C-20 integracion-e2e    ← + C-11, C-12, C-17
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 (solo)

GATE 1: C-01 ✓                                    ← PRIMER FORK (3 paralelos, cap. 2-3)
  → C-02 http-contracts-and-errors                [Agente A]
  → C-03 async-crypto                             [Agente B]
  → C-04 background-notifications                 [Agente C]

GATE 2: C-02 ✓
  → C-05 database-lifecycle                       [Agente A]

GATE 3: C-05 ✓
  → C-06 auth-models                              [Agente A]

GATE 4: C-06 ✓                                    ← FORK (2 paralelos, cap. 4-5)
  → C-07 domain-models                            [Agente A]
  → C-09 auth-login-jwt                           [Agente B — si C-03 ✓]

GATE 5: C-07 ✓                                    ← FORK (2 paralelos)
  → C-08 seed-inicial                             [Agente A — si C-03 ✓]
  → C-13 repositories                             [Agente C — si C-09 ✓]

GATE 6: C-09 ✓                                    ← FORK (3 paralelos, cap. 5)
  → C-10 rbac-route-groups                        [Agente A]
  → C-11 password-lifecycle                       [Agente B]
  → C-13 repositories                             [Agente C — si C-07 ✓]

GATE 7: C-13 ✓ / C-10 ✓
  → C-14 unit-of-work                             [Agente C]
  → C-12 admin-usuarios-roles                     [Agente A — si C-10 ✓]

GATE 8: C-14 ✓                                    ← FORK (3 paralelos, cap. 6)
  → C-15 clientes-vehiculos                       [Agente A]
  → C-16 repuestos-stock                          [Agente B]
  → C-17 registro-atomico                         [Agente C — si C-15 ✓]

GATE 9: C-15 + C-16 ✓
  → C-18 ordenes-apertura-consulta                [Agente A]

GATE 10: C-18 ✓ (+ C-04 ✓)
  → C-19 ordenes-transiciones                     [Agente A]

GATE 11: C-19 ✓ (y C-11 + C-12 + C-17 ✓)
  → C-20 integracion-e2e                          [Agente B]
```

### Camino crítico (11 changes — mínimo irreducible)

```
C-01 → C-02 → C-05 → C-06 → C-07 → C-13 → C-14 → C-16 → C-18 → C-19 → C-20
```

> `C-09 auth-login-jwt` también es indispensable para producción, pero corre en paralelo con `C-07`, por lo que no alarga la cadena. `C-19` y `C-20`* son el último eslabón: sin transiciones de orden ni verificación de contrato no hay entrega.

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Core / Persistencia) │ Agente B (Seguridad)         │ Agente C (Dominio / Integración)
─────┼─────────────────────────────────┼──────────────────────────────┼──────────────────────────────────
  1  │ C-01 foundation-setup           │ —                            │ —
  2  │ C-02 http-contracts-and-errors  │ C-03 async-crypto            │ C-04 background-notifications
  3  │ C-05 database-lifecycle         │ —                            │ —
  4  │ C-06 auth-models                │ —                            │ —
  5  │ C-07 domain-models              │ C-09 auth-login-jwt          │ —
  6  │ C-08 seed-inicial               │ C-10 rbac-route-groups       │ C-13 repositories
  7  │ C-12 admin-usuarios-roles       │ C-11 password-lifecycle      │ C-14 unit-of-work
  8  │ C-15 clientes-vehiculos         │ C-16 repuestos-stock         │ C-17 registro-atomico
  9  │ C-18 ordenes-apertura-consulta  │ C-20 (armado de .http)       │ —
 10  │ C-19 ordenes-transiciones       │ C-20 (smoke E2E)             │ —
 11  │ —                               │ C-20 integracion-e2e (cierre)│ —
```

> Los `.http` de integración se escriben dentro de cada change; `C-20` sólo consolida y verifica. El agente que quede libre en los pasos 3-5 adelanta los fixtures de test del módulo que viene.

---

## FASE 0 — Capítulo 1: Cimientos de la API

### [C-01] `foundation-setup`
- **Estado**: `[x]` completado
- **Scope**: Scaffolding del proyecto + configuración base, sin lógica de negocio
  - Estructura: `app/core/`, `app/modules/{health,usuarios,clientes,repuestos,ordenes}/` (con `__init__.py`), `migrations/`, `test/`
  - `requirements.txt` (o `pyproject.toml`) con versiones fijadas: FastAPI ≥0.111, SQLModel 0.0.24, SQLAlchemy 2.0 async, asyncpg 0.30, Alembic 1.13, pydantic-settings 2.0, bcrypt 4.0, PyJWT 2.8, uvicorn[standard], pytest, pytest-asyncio, httpx
  - `app/core/config.py`: `Settings(BaseSettings)` con `database_url`, `jwt_secret`, `access_token_ttl_min`, `bcrypt_max_concurrency`, `login_max_intentos`, `login_ventana_seg`, `entorno`; `.env.example` versionado y `.env` en `.gitignore`
  - `main.py`: `create_app()` con `lifespan` vacío preparado (hooks documentados), logging estructurado, router raíz
  - `app/modules/health/router.py`: `GET /health/live` → `200` sin tocar la base
  - `test/health.http` + `test/conftest.py` con `httpx.AsyncClient`/`ASGITransport`
  - `README.md`: comandos de instalación, `uvicorn app.main:app --reload`, `pytest`
  - Tests: `/health/live` 200, arranque sin `JWT_SECRET` falla con error explícito, `/openapi.json` 200
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` §Visión y §Alcance
  - `knowledge-base/02_descripcion_general.md` §Pila Tecnológica Obligatoria, §Estructura Obligatoria del Proyecto
  - `knowledge-base/08_arquitectura_propuesta.md` §Ciclo de Vida
  - `knowledge-base/09_decisiones_y_supuestos.md` §4 (bcrypt fuera del event loop)

---

## FASE 1 — Capítulo 2: Contratos, validación y semántica HTTP

### [C-02] `http-contracts-and-errors`
- **Estado**: `[x]` completado
- **Scope**: Contrato transversal de entrada/salida y traducción de errores a códigos HTTP
  - `app/core/errors.py`: `AppError` base + `ConflictoError`, `NoEncontradoError`, `ProhibidoError`, `NoAutenticadoError`, `ReglaNegocioError`, `DemasiadasPeticionesError` (con `retry_after`)
  - Handlers en `main.py`: mapping → `400 / 401 / 403 / 404 / 409 / 422 / 429`; cuerpo uniforme `{"detail", "codigo"}`; cabecera `Retry-After` cuando aplique
  - Traducción de `IntegrityError` (UNIQUE/FK) → `409` con mensaje de dominio, sin nombre de constraint ni traza (RN-18); `RequestValidationError` → `422` con lista de campos
  - `app/core/paginacion.py`: `PageParams` (`page >= 1`, `size` entre 1 y 100, defaults), `Page[T]` genérico (`items, total, page, size`)
  - Convención `model_config = ConfigDict(extra="forbid")` en todos los schemas de entrada + normalización de strings (`strip`) y `EmailStr`
  - Tests: campo extra → 422, `IntegrityError` simulado → 409 sin detalles internos, formato uniforme de error, `Page[T]` serializa total/página
- **Dependencias**: `C-01`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01, §RN-10, §RN-18
  - `knowledge-base/06_funcionalidades.md` (códigos HTTP declarados por endpoint)
  - `knowledge-base/08_arquitectura_propuesta.md` §Router (traducción de excepciones)
  - `knowledge-base/09_decisiones_y_supuestos.md` §2 (índices parciales y errores de unicidad)

---

## FASE 2 — Capítulo 3: Asincronía sin bloqueos

### [C-03] `async-crypto`
- **Estado**: `[x]` completado
- **Scope**: Criptografía de contraseñas no bloqueante, reutilizable por auth y seed
  - `app/core/security.py`: `hash_password()` / `verify_password()` envolviendo `bcrypt` en `asyncio.to_thread`, protegidas por un `asyncio.Semaphore(settings.bcrypt_max_concurrency)` creado en `lifespan` (`app.state`)
  - `hash_password_sync()` para uso exclusivo de `seed.py`/CLI (documentado: nunca dentro de un handler)
  - `generar_hash_ficticio()` al arrancar + `verify_password_o_dummy(hash_real | None, plain, dummy)` con tiempo de respuesta constante (RN-09)
  - Tests: 20 verificaciones concurrentes no bloquean el event loop (latencia de un endpoint trivial < umbral durante la carga), el semáforo limita la concurrencia real, dummy hash siempre devuelve `False`, `hash_password` produce hashes verificables
- **Dependencias**: `C-01`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/09_decisiones_y_supuestos.md` §4 (to_thread + semáforo)
  - `knowledge-base/07_flujos_principales.md` §2 Flujo de Autenticación y Login
  - `knowledge-base/05_reglas_de_negocio.md` §RN-09
  - `knowledge-base/02_descripcion_general.md` §Pila Tecnológica (bcrypt 4.0)

---

### [C-04] `background-notifications`
- **Estado**: `[x]` completado
- **Scope**: Aviso al cliente al terminar una orden, desacoplado del request y sin reutilizar la sesión
  - `app/core/notificaciones.py`: `NotificadorCliente` (Protocol) + `BackgroundTasksNotifier.notificar_orden_terminada(orden_id)` con `await asyncio.sleep(0.5)` y log estructurado
  - Contrato explícito: la tarea se agenda **después** del commit del Unit of Work y **no recibe** `AsyncSession` (evita usar una sesión ya cerrada); los datos necesarios se pasan como valores (ids, email, total)
  - Manejo de excepción dentro de la tarea: se loguea y no afecta la respuesta ya emitida
  - Tests: la tarea se ejecuta y loguea, no abre conexión a base, un fallo en la tarea no altera el `200` del endpoint que la agendó
- **Dependencias**: `C-01`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §3 Terminación de orden
  - `knowledge-base/10_preguntas_abiertas.md` §2 (colas fuera de alcance, pérdida asumida)
  - `knowledge-base/01_vision_y_objetivos.md` §Alcance
  - `knowledge-base/06_funcionalidades.md` §6 Órdenes de Trabajo

---

## FASE 3 — Capítulo 4: Persistencia, migraciones y seed

### [C-05] `database-lifecycle`
- **Estado**: `[x]` completado
- **Scope**: Motor asincrónico, sesión por request, health de readiness y base de Alembic
  - `app/core/database.py`: `create_async_engine(database_url, pool_pre_ping=True)` + `async_sessionmaker(expire_on_commit=False)`, guardados en `app.state` durante `lifespan`; `engine.dispose()` al apagar
  - `get_session()` dependency: una sesión por request, `async with` y cierre garantizado; **no** hace `commit()` (eso es del UoW)
  - `GET /health/ready`: `SELECT 1` → `200`, y `503` si la base no responde (timeout acotado)
  - `alembic.ini` + `migrations/env.py` con plantilla **asíncrona** leyendo `Settings.database_url`; `migrations/script.py.mako`
  - `test/conftest.py`: engine de test por sesión de pytest, base efímera, transacción con rollback por test, override de `get_session`
  - Tests: `/health/ready` 200 con DB y 503 con URL inválida, sesión se cierra al final del request, `alembic upgrade head` corre sin error
- **Dependencias**: `C-01`, `C-02`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Ciclo de Vida (`main.py` y `database.py`)
  - `knowledge-base/04_modelo_de_datos.md` (encabezado: Alembic asincrónico obligatorio)
  - `knowledge-base/02_descripcion_general.md` §Pila Tecnológica (asyncpg, Alembic)
  - `knowledge-base/06_funcionalidades.md` §1 Health

---

### [C-06] `auth-models`
- **Estado**: `[ ]` pendiente
- **Scope**: Modelos y migración de las tablas de identidad, roles y auditoría de acceso
  - Modelos SQLModel: `Usuario` (`email` UNIQUE, `password_hash`, `activo`, `debe_cambiar_password`, `password_cambiada_en` timestamptz nullable), `AsignacionRol` (`rol` con CHECK `ADMIN|RECEPCION|MECANICO|CLIENTE`, `desde`, `vence_en`, `revocada_en`, `otorgada_por`), `IntentoAcceso` (`cuando`, `email`, `ip`, `exito`), `EventoSeguridad` (`cuando`, `actor`, `accion`)
  - Relaciones: `Usuario.asignaciones` ↔ `AsignacionRol.usuario` con `back_populates`; `lazy="raise"` para forzar precarga explícita
  - Migración `001_auth_core` revisada a mano: índice único parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL` (RN-03) e índice `ix_intento_acceso_email_ip_cuando (email, ip, cuando)`
  - Tests: segundo rol abierto del mismo tipo → `IntegrityError` → 409; email duplicado → 409; `CHECK` de rol inválido rechazado; `ROLLBACK` de `alembic downgrade base`
- **Dependencias**: `C-05`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 1-4 (`usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`)
  - `knowledge-base/03_actores_y_roles.md` §Gestión de Roles y Autenticación
  - `knowledge-base/09_decisiones_y_supuestos.md` §2, §3
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01, §RN-03, §RN-05

---

### [C-07] `domain-models`
- **Estado**: `[ ]` pendiente
- **Scope**: Modelos y migraciones del dominio del taller + disparadores de sólo agregado
  - Modelos: `Cliente` (`usuario_id` UNIQUE nullable), `Vehiculo` (`borrado_en`, CHECK `anio` 1950-2100), `Repuesto` (`borrado_en`, CHECK `precio > 0`, `stock >= 0`), `EstadoOrden` (PK `codigo`, `posicion` UNIQUE, `es_final`), `OrdenTrabajo` (FK `estado` → `estado_orden.codigo`, `mecanico_id` nullable, `total >= 0`), `ItemOrden` (UNIQUE `(orden_id, repuesto_id)`, `cantidad > 0`), `HistorialEstadoOrden`, `MovimientoStock` (`cantidad != 0`), `HistorialPrecioRepuesto` (CHECK `precio_nuevo > precio_anterior`)
  - Relaciones bidireccionales completas con `back_populates` y `lazy="raise"`; colecciones de composición con `cascade="all, delete-orphan"` donde corresponda (`ItemOrden`)
  - Migración `002_dominio_taller`: FKs, CHECKs e índices únicos parciales `uq_vehiculo_patente_vigente (patente) WHERE borrado_en IS NULL` y `uq_repuesto_codigo_vigente (codigo) WHERE borrado_en IS NULL`
  - Migración `003_solo_agregado` escrita a mano: función + `TRIGGER BEFORE UPDATE OR DELETE` en `movimiento_stock`, `historial_estado_orden`, `historial_precio_repuesto` (RN-15) + `test/solo_agregado.sql`
  - Tests: `UPDATE`/`DELETE` sobre tablas de sólo agregado falla, patente reutilizable tras baja lógica, ítem repetido en la misma orden rechazado, CHECK de año/precio/stock
- **Dependencias**: `C-06`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 5-13, §Características Clave
  - `knowledge-base/09_decisiones_y_supuestos.md` §1, §2
  - `knowledge-base/08_arquitectura_propuesta.md` §Model
  - `knowledge-base/05_reglas_de_negocio.md` §RN-15, §RN-16, §RN-19
  - `knowledge-base/02_descripcion_general.md` §Estructura Obligatoria (`test/solo_agregado.sql`)

---

### [C-08] `seed-inicial`
- **Estado**: `[ ]` pendiente
- **Scope**: Carga reproducible del estado inicial conocido de la base
  - `seed.py` idempotente (verifica existencia antes de insertar; `--reset` documentado para recrear)
  - Catálogo `estado_orden`: `PENDIENTE` (1), `EN_REPARACION` (2), `TERMINADA` (3, `es_final=true`), `CANCELADA` (4, `es_final=true`) (RN-19)
  - Usuarios base ADMIN / RECEPCION / MECANICO / CLIENTE con contraseña hasheada vía `hash_password_sync` y roles en `asignacion_rol`; al menos un usuario con `debe_cambiar_password=True`
  - Repuestos con stock inicial + `movimiento_stock` de motivo `ALTA` (RN-14); clientes, vehículos y 2-3 órdenes demo en distintos estados con su línea inicial de historial
  - Registro en `evento_seguridad` con `actor = 'SISTEMA'`
  - Tests: `seed.py` dos veces seguidas no duplica filas, catálogo con `posicion` correcta, órdenes demo respetan `estado_orden`
- **Dependencias**: `C-03`, `C-07`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/02_descripcion_general.md` §Estructura Obligatoria (`seed.py`)
  - `knowledge-base/04_modelo_de_datos.md` §Tabla 8 (`estado_orden`)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-14, §RN-19
  - `knowledge-base/03_actores_y_roles.md` §Sistema (`SISTEMA`)

---

## FASE 4 — Capítulo 5: Autenticación, autorización y roles

### [C-09] `auth-login-jwt`
- **Estado**: `[ ]` pendiente
- **Scope**: Login con JWT en cookie HttpOnly, rate limit de intentos y sesión actual
  - `POST /auth/login`: cuenta `intento_acceso` fallidos por `(email, ip)` en los últimos 60 s; si ≥ 5 → `429` + `Retry-After` **sin** calcular hash (RN-08)
  - Búsqueda por email + `verify_password_o_dummy` (RN-09, C-03); usuario inactivo → `401` uniforme
  - JWT HS256 firmado con `sub`, `iat`, `exp`, `roles` (informativos, RN-04); cookie `access_token` con `HttpOnly`, `SameSite=Lax`, `max_age = TTL`, `secure` según entorno
  - El intento de acceso se registra en una sesión/transacción **independiente** que commitea siempre, incluso si el login falla (KB §09.5)
  - `POST /auth/logout` (borra cookie) y `GET /auth/yo` (usuario, roles vigentes, `iat`/`exp` del token)
  - `get_current_user` dependency: valida cookie, firma, `exp` y compara `iat` con `password_cambiada_en` (RN-07, precisión de microsegundos)
  - `evento_seguridad`: `LOGIN_OK`, `LOGIN_FALLIDO`, `LOGIN_BLOQUEADO`, `LOGOUT`
  - Tests: login correcto setea cookie HttpOnly, credenciales inválidas 401, quinto fallo → 429 con `Retry-After` y sin hash, token expirado 401, `iat` previo al cambio de password 401, respuesta idéntica para email inexistente
- **Dependencias**: `C-02`, `C-03`, `C-05`, `C-06`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §2 Flujo de Autenticación y Login
  - `knowledge-base/05_reglas_de_negocio.md` §RN-04, §RN-07, §RN-08, §RN-09
  - `knowledge-base/03_actores_y_roles.md` §Gestión de Roles y Autenticación
  - `knowledge-base/09_decisiones_y_supuestos.md` §4, §5
  - `knowledge-base/06_funcionalidades.md` §2 Autenticación

---

### [C-10] `rbac-route-groups`
- **Estado**: `[ ]` pendiente
- **Scope**: Autorización por roles vigentes en base de datos + separación de grupos de rutas
  - `app/core/dependencies.py`: `get_roles_vigentes(usuario_id)` consulta `asignacion_rol` con `revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())` **en cada request** (RN-04); los roles del JWT se ignoran para decidir
  - `require_roles(*roles)` factory: sin credencial → `401`, con credencial sin rol → `403`; decorador/dependencia reutilizable por router
  - Helpers de propiedad: `es_duenio_de_vehiculo(usuario_id, vehiculo_id)` y `es_duenio_de_orden(...)` para RN-17
  - `main.py`: `router_publico` (`/health/*`, `/auth/registro`, `/auth/login`) y `router_protegido` (resto); gating de `debe_cambiar_password` → `403` en rutas protegidas salvo `/auth/*` y `/health/*` (RN-06)
  - Tests: rol revocado en caliente pierde acceso en la request siguiente, `vence_en` en el pasado no autoriza, 401 vs 403 correctos, usuario con password pendiente bloqueado en rutas de dominio y habilitado en `/auth/*`
- **Dependencias**: `C-09`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §Gestión de Roles y Autenticación (RN-04, RN-05)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-04, §RN-06, §RN-17
  - `knowledge-base/04_modelo_de_datos.md` §Tabla 2 (`asignacion_rol`)
  - `knowledge-base/07_flujos_principales.md` §2

---

### [C-11] `password-lifecycle`
- **Estado**: `[ ]` pendiente
- **Scope**: Cambio de contraseña y expiración de sesiones anteriores
  - `POST /auth/cambiar-password`: valida contraseña actual (401 uniforme si falla), hashea en `to_thread`, persiste `password_cambiada_en = now()` sin truncar fracciones y `debe_cambiar_password = False` (RN-07)
  - Invalidación: cualquier JWT con `iat` anterior a `password_cambiada_en` → `401` (reutiliza la verificación de C-09)
  - Schema de entrada con `extra="forbid"` y regla de complejidad mínima → `422`
  - `evento_seguridad`: `PASSWORD_CAMBIADA`
  - Tests: token previo inválido tras el cambio, token emitido después válido, contraseña actual incorrecta 401 sin revelar existencia del usuario, cambio exitoso levanta `debe_cambiar_password`
- **Dependencias**: `C-09`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-06, §RN-07
  - `knowledge-base/04_modelo_de_datos.md` §Tabla 1 (`usuario`)
  - `knowledge-base/06_funcionalidades.md` §2 (`/auth/cambiar-password`)
  - `knowledge-base/03_actores_y_roles.md` §Vigencia y Revocación

---

### [C-12] `admin-usuarios-roles`
- **Estado**: `[ ]` pendiente
- **Scope**: Gestión de personal, asignación/revocación de roles y auditoría (sólo ADMIN)
  - `POST /usuarios`: alta de personal con contraseña provisoria (`debe_cambiar_password=True`), 409 email duplicado, 422 contrato
  - `GET /usuarios/{id}/roles`: historial de asignaciones (vigentes y revocadas), 404 inexistente
  - `POST /usuarios/{id}/roles`: asignación con `vence_en` opcional y `otorgada_por` = admin actual; doble asignación abierta → 409 (RN-03)
  - `DELETE /usuarios/{id}/roles/{rol}`: revocación con `revocada_en = now()` sin borrar la fila; autoprotección RN-05 (no revocar el propio ADMIN, no dejar el sistema sin admins vigentes) → 409
  - `GET /eventos`: auditoría paginada (ADMIN) con filtros por fecha y actor
  - `evento_seguridad`: `USUARIO_CREADO`, `ROL_ASIGNADO`, `ROL_REVOCADO`
  - Tests: auto-revocación 409, último admin 409, reasignación de rol vencido abre fila nueva, paginación de `/eventos`, endpoints rechazan no-ADMIN con 403
- **Dependencias**: `C-10`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §Vigencia y Revocación, §Autoprotección
  - `knowledge-base/06_funcionalidades.md` §3 Usuarios y Roles
  - `knowledge-base/05_reglas_de_negocio.md` §RN-03, §RN-05
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 2 y 4

---

## FASE 5 — Capítulo 6: Repositorios, Unit of Work y transacciones

### [C-13] `repositories`
- **Estado**: `[ ]` pendiente
- **Scope**: Jerarquía de repositorios genéricos + repositorios concretos de identidad
  - `app/core/repository.py`: `BaseRepository[T]` con `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `add`/`update` ejecutan `flush()` y **nunca** `commit()`
  - `SoftDeleteRepository[T]`: filtra `borrado_en IS NULL` por defecto, agrega `get_by_id_including_deleted` y `soft_delete()`
  - Precarga explícita con `selectinload` en todo método que devuelva agregados (sin N+1, sin lazy loading)
  - Repositorios piloto: `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository`, `EventoSeguridadRepository`; constructor tipado sobre `AsyncSession`
  - Refactor de `app/modules/usuarios` (C-09/C-12) para consumir los repositorios **sin cambiar contratos HTTP ni códigos de respuesta**
  - Tests: contador de queries demuestra precarga (sin N+1), `add` no commitea (visible sólo tras commit externo), soft delete excluye del listado y `get_by_id_including_deleted` lo encuentra
- **Dependencias**: `C-07`, `C-09`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Repository
  - `knowledge-base/09_decisiones_y_supuestos.md` §2 (borrado lógico e índices parciales)
  - `knowledge-base/04_modelo_de_datos.md` §Características Clave
  - `knowledge-base/02_descripcion_general.md` §Estructura Obligatoria (`app/core/repository.py`)

---

### [C-14] `unit-of-work`
- **Estado**: `[ ]` pendiente
- **Scope**: Unidad de trabajo asincrónica que agrupa repositorios sobre una única sesión
  - `app/core/unit_of_work.py`: `UnitOfWork` como gestor de contexto asincrónico; expone repositorios como propiedades; `__aexit__` → `commit()` si no hubo excepción, `rollback()` si la hubo; **no cierra** la sesión (la creó `get_session`)
  - `get_uow()` dependency: un UoW por request construido sobre la sesión inyectada
  - `app/modules/usuarios/unit_of_work.py` como implementación de referencia (y único punto de commit del módulo)
  - Regla documentada de sub-UoW: sólo permitido para auditoría independiente (`intento_acceso`), nunca para escrituras de dominio
  - Tests: commit en éxito, rollback deja la base intacta ante excepción, sesión sigue abierta tras salir del bloque, excepción de negocio no deja escrituras parciales, dos servicios no comparten UoW
- **Dependencias**: `C-13`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Unit of Work, §Service
  - `knowledge-base/07_flujos_principales.md` §1 (bloque único de UoW), §3
  - `knowledge-base/05_reglas_de_negocio.md` §RN-02, §RN-13, §RN-20
  - `knowledge-base/02_descripcion_general.md` §Estructura Obligatoria (`unit_of_work.py`)

---

### [C-15] `clientes-vehiculos`
- **Estado**: `[ ]` pendiente
- **Scope**: Módulo de clientes y vehículos con borrado lógico y control de propiedad
  - `app/modules/clientes/`: `schemas.py`, `repository.py` (`ClienteRepository`, `VehiculoRepository(SoftDeleteRepository)`), `unit_of_work.py`, `service.py`, `router.py`
  - Endpoints: `POST /clientes` (RECEPCION, ADMIN), `GET /clientes/{id}` con vehículos precargados, `POST /clientes/{id}/vehiculos`, `DELETE /vehiculos/{id}` → `204`, `GET /mis-vehiculos`
  - RN-16: no dar de baja un vehículo con órdenes abiertas (`estado_orden.es_final = false`) → `409`; RN-17: `/mis-vehiculos` sólo devuelve vehículos del cliente autenticado
  - RN-01: documento UNIQUE y patente única vigente → `409`; `404` para cliente/vehículo inexistente o dado de baja
  - Tests: alta y consulta con vehículos, patente duplicada vigente 409, patente reusable tras baja lógica, baja con orden abierta 409, cliente no ve vehículos ajenos, 403 sin rol
- **Dependencias**: `C-10`, `C-14`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 5-6 (`cliente`, `vehiculo`)
  - `knowledge-base/06_funcionalidades.md` §4 Clientes y Vehículos
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01, §RN-16, §RN-17
  - `knowledge-base/09_decisiones_y_supuestos.md` §2

---

### [C-16] `repuestos-stock`
- **Estado**: `[ ]` pendiente
- **Scope**: Catálogo de repuestos con stock gobernado exclusivamente por movimientos
  - `app/modules/repuestos/`: `RepuestoRepository(SoftDeleteRepository)`, `MovimientoStockRepository`, `HistorialPrecioRepuestoRepository`, uow, service, router
  - Endpoints: `GET /repuestos` (`q`, `page`, `size`), `GET /repuestos/{id}`, `POST /repuestos` (ADMIN, stock inicial + `movimiento_stock ALTA` en el mismo UoW), `PATCH /repuestos/{id}` (descripción y/o precio), `DELETE /repuestos/{id}` (`204`, lógico), `POST /repuestos/{id}/reponer`, `GET /repuestos/{id}/movimientos`, `GET /repuestos/{id}/precios`
  - RN-14: `stock` no es editable por `PATCH`; todo cambio pasa por `movimiento_stock` (rechazo con `422`/`400`)
  - RN-20: `PATCH` con precio distinto → línea en `historial_precio_repuesto` en la misma transacción; sin cambio → no genera línea; `precio_nuevo <= precio_anterior` → `409`
  - Paginación con `Page[T]` y búsqueda `ILIKE` por descripción
  - Tests: alta genera movimiento ALTA, reposición genera movimiento, PATCH sin cambio no genera historial, precio menor rechazado, stock nunca negativo, 404 en dado de baja, sólo ADMIN muta
- **Dependencias**: `C-10`, `C-14`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 7, 12, 13
  - `knowledge-base/06_funcionalidades.md` §5 Repuestos y Stock
  - `knowledge-base/05_reglas_de_negocio.md` §RN-14, §RN-20
  - `knowledge-base/07_flujos_principales.md` §3

---

### [C-17] `registro-atomico`
- **Estado**: `[ ]` pendiente
- **Scope**: Auto-registro público con escritura atómica de tres entidades
  - `POST /auth/registro`: un único `UnitOfWork` que crea `Usuario` + `AsignacionRol(CLIENTE)` + `Cliente` (RN-02); un solo `commit` o `rollback` total
  - El hash de contraseña se calcula **antes** de abrir la transacción (no retener conexión durante bcrypt)
  - `409` por email o documento duplicado sin dejar usuario ni rol huérfanos; `422` por contrato inválido
  - `201` con cuerpo sin `password_hash`; `evento_seguridad`: `USUARIO_AUTO_REGISTRADO`
  - Tests: fallo al crear el cliente revierte usuario y rol (0 filas en las 3 tablas), alta exitosa 201 + login inmediato, documento duplicado 409 sin residuos, dos registros concurrentes con el mismo email → uno solo persiste
- **Dependencias**: `C-09`, `C-14`, `C-15`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §1 Flujo de Auto-Registro
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01, §RN-02
  - `knowledge-base/08_arquitectura_propuesta.md` §Unit of Work, §Service
  - `knowledge-base/06_funcionalidades.md` §2 (`/auth/registro`)

---

### [C-18] `ordenes-apertura-consulta`
- **Estado**: `[ ]` pendiente
- **Scope**: Apertura de órdenes con precio y total calculados en servidor + consultas de órdenes
  - `app/modules/ordenes/`: `OrdenRepository`, `ItemOrdenRepository`, `EstadoOrdenRepository` (sólo lectura), `HistorialEstadoOrdenRepository`, uow, service, router
  - Schemas de entrada sin `precio_unitario` ni `total` (`extra="forbid"`); ítems sin repetir y `cantidad > 0` → `422` (RN-10)
  - `POST /ordenes`: valida repuestos vigentes (RN-16), copia `precio_unitario` actual, calcula `total` en servidor, crea orden `PENDIENTE` + línea de historial `desde_estado=NULL → PENDIENTE` en el mismo UoW; catálogo vacío → `409` (RN-19)
  - Consultas: `GET /ordenes` (`estado`, `page`, `size`), `GET /ordenes/{id}` (personal o dueño; `403` si no corresponde, `404` inexistente), `GET /mis-ordenes`, `GET /estados-orden` ordenado por `posicion`
  - Precarga con `selectinload` de `vehiculo`, `items.repuesto` y `mecanico` (sin N+1)
  - Tests: total calculado ignorando cualquier precio enviado, ítem repetido 422, repuesto dado de baja 409, orden sin ítems 422, dueño ve su orden y ajeno 403, filtro por estado y paginación, `/estados-orden` en orden de `posicion`
- **Dependencias**: `C-15`, `C-16`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §6 Órdenes de Trabajo
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 8-11
  - `knowledge-base/05_reglas_de_negocio.md` §RN-10, §RN-16, §RN-17, §RN-19
  - `knowledge-base/07_flujos_principales.md` §3 Apertura
  - `knowledge-base/08_arquitectura_propuesta.md` §Repository (precarga explícita)

---

### [C-19] `ordenes-transiciones`
- **Estado**: `[ ]` pendiente
- **Scope**: Inicio, terminación con descuento atómico de stock y cancelación de órdenes
  - `POST /ordenes/{id}/iniciar`: asigna el mecánico autenticado si la orden no tiene uno, `PENDIENTE → EN_REPARACION`, línea de historial; transición inválida → `409` (RN-11)
  - `POST /ordenes/{id}/terminar`: UoW único → verifica stock de cada ítem, descuenta `repuesto.stock`, registra `movimiento_stock` (cantidad negativa, motivo `TERMINACION`), pasa a `TERMINADA` y agrega historial; stock insuficiente → `rollback` total + `409` (RN-13)
  - `POST /ordenes/{id}/cancelar`: evalúa permisos (RECEPCION / ADMIN / dueño del vehículo) **antes** de validar el estado (RN-12) → `403` si no corresponde, `409` si ya es final; no toca stock
  - Tras el commit exitoso de `terminar`, agenda `NotificadorCliente` en `BackgroundTasks` (C-04) pasando sólo valores, nunca la sesión
  - Tests: terminar sin stock 409 con stock y estado intactos, terminar ok descuenta y genera un movimiento por ítem, doble terminar 409, cancelar orden ajena 403, orden final no transiciona, la notificación se agenda sólo después del commit
- **Dependencias**: `C-04`, `C-18`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §3 Inicio y Terminación
  - `knowledge-base/05_reglas_de_negocio.md` §RN-11, §RN-12, §RN-13, §RN-14
  - `knowledge-base/04_modelo_de_datos.md` §Tablas 9-12
  - `knowledge-base/08_arquitectura_propuesta.md` §Service, §Unit of Work
  - `knowledge-base/10_preguntas_abiertas.md` §1, §2

---

## FASE 6 — Integración y cierre del TP

### [C-20] `integracion-e2e`
- **Estado**: `[ ]` pendiente
- **Scope**: Verificación end-to-end del contrato completo y guía de ejecución
  - `test/*.http` por módulo (`health`, `auth`, `usuarios`, `clientes`, `repuestos`, `ordenes`) con variables de entorno, cookie `access_token` y casos felices + errores declarados
  - Suite pytest de contrato: cada endpoint de `06_funcionalidades.md` responde el código esperado, y cada regla RN-01…RN-20 tiene al menos un test que la ejerce
  - Smoke E2E del flujo completo: registro → login → alta cliente/vehículo → alta de orden → iniciar → terminar → consulta `/mis-ordenes` y `/repuestos/{id}/movimientos`
  - Verificación RN-15 sobre base real: `UPDATE`/`DELETE` en las tres tablas de sólo agregado falla, ejecutando `test/solo_agregado.sql`
  - `README.md` final: variables de entorno, `alembic upgrade head`, `python seed.py`, `pytest`, arranque con uvicorn; script `scripts/verificar` (lint + tests + smoke)
  - Tests: suite completa verde sobre base recién migrada y sembrada, sin warnings de sesión abierta
- **Dependencias**: `C-11`, `C-12`, `C-17`, `C-19`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` (todos los módulos y códigos HTTP)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01 a §RN-20
  - `knowledge-base/07_flujos_principales.md` (los 3 flujos)
  - `knowledge-base/02_descripcion_general.md` §Estructura Obligatoria (`test/`)
  - `knowledge-base/10_preguntas_abiertas.md` (limitaciones asumidas)

---

## Tabla resumen de changes

| ID | Change | Fase / Cap. | Depende de | Governance |
|----|--------|-------------|------------|------------|
| C-01 | `foundation-setup` | 0 / cap. 1 | — | BAJO |
| C-02 | `http-contracts-and-errors` | 1 / cap. 2 | C-01 | MEDIO |
| C-03 | `async-crypto` | 2 / cap. 3 | C-01 | ALTO |
| C-04 | `background-notifications` | 2 / cap. 3 | C-01 | MEDIO |
| C-05 | `database-lifecycle` | 3 / cap. 4 | C-01, C-02 | ALTO |
| C-06 | `auth-models` | 3 / cap. 4 | C-05 | CRITICO |
| C-07 | `domain-models` | 3 / cap. 4 | C-06 | CRITICO |
| C-08 | `seed-inicial` | 3 / cap. 4 | C-03, C-07 | MEDIO |
| C-09 | `auth-login-jwt` | 4 / cap. 5 | C-02, C-03, C-05, C-06 | CRITICO |
| C-10 | `rbac-route-groups` | 4 / cap. 5 | C-09 | ALTO |
| C-11 | `password-lifecycle` | 4 / cap. 5 | C-09 | ALTO |
| C-12 | `admin-usuarios-roles` | 4 / cap. 5 | C-10 | ALTO |
| C-13 | `repositories` | 5 / cap. 6 | C-07, C-09 | CRITICO |
| C-14 | `unit-of-work` | 5 / cap. 6 | C-13 | CRITICO |
| C-15 | `clientes-vehiculos` | 5 / cap. 6 | C-10, C-14 | MEDIO |
| C-16 | `repuestos-stock` | 5 / cap. 6 | C-10, C-14 | ALTO |
| C-17 | `registro-atomico` | 5 / cap. 6 | C-09, C-14, C-15 | CRITICO |
| C-18 | `ordenes-apertura-consulta` | 5 / cap. 6 | C-15, C-16 | ALTO |
| C-19 | `ordenes-transiciones` | 5 / cap. 6 | C-04, C-18 | CRITICO |
| C-20 | `integracion-e2e` | 6 / cierre | C-11, C-12, C-17, C-19 | MEDIO |

**Total**: 20 changes en 7 fases (FASE 0 a FASE 6).
**Camino crítico**: 11 changes.
**Gates de paralelismo**: 12 (GATE 0 a GATE 11).
**Primer change recomendado**: `C-01` (`foundation-setup`).

> Para arrancar: `/opsx:propose C-01-foundation-setup`
