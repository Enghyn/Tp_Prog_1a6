# Taller Mecánico API — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Stack Tecnológico

| Capa | Tecnología | Versión |
|------|------------|---------|
| Lenguaje | Python | 3.12 |
| Framework web | FastAPI (`async def` en todos los handlers) | 0.111 |
| Modelos / ORM | SQLModel + SQLAlchemy 2.0 (async, `selectinload`) | 0.0.24 / 2.0 |
| Driver | asyncpg | 0.30 |
| Base de datos | PostgreSQL | 16 |
| Migraciones | Alembic (plantilla asincrónica) | 1.13 |
| Config | pydantic-settings (`.env`) | 2.0 |
| Seguridad | bcrypt + PyJWT | 4.0 / 2.8 |
| Servidor | Uvicorn (`fastapi[standard]`) | — |

Detalle completo (incluye la estructura obligatoria de 6 capas): [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Entender propósito, alcance y qué queda fuera |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, estructura de carpetas, dominio |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, `asignacion_rol`, rutas públicas |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, restricciones, índices parciales |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas (RN-01 a RN-20) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Módulos y endpoints de referencia |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E (registro, login, órdenes, stock) |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Capas, Unit of Work, repositorios, ciclo de vida |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones de diseño y justificaciones |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Limitaciones deliberadas (cap. 7 y 8 fuera de alcance) |

> `10_preguntas_abiertas.md` no tiene bloqueantes abiertos: documenta limitaciones **aceptadas** (concurrencia avanzada y colas). Leelo antes de proponer cambios de alcance.

---

## Skills Disponibles

Fuente de verdad: `.atl/skill-registry.md` (generado por `skill-registry`). Estas 8 skills están instaladas **localmente** en `.agents/skills/`:

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | Endpoints, modelos, repositorios, UoW | `fastapi`, `fastapi-templates`, `python-design-patterns`, `postgresql-table-design` |
| **Auth y Seguridad** | JWT, cookies, RBAC, hashing | `auth-implementation-patterns`, `fastapi` |
| **Async y Background** | `to_thread`, semáforos, `BackgroundTasks` | `async-python-patterns`, `python-background-jobs` |
| **Testing** | pytest async, fixtures, DB real | `python-testing-patterns` |
| **Orquestación / SDD** | Propose, apply, archive, sync | `openspec-propose`, `openspec-apply-change`, `openspec-archive-change`, `openspec-sync-specs`, `openspec-update-change`, `openspec-explore` |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 20 changes en 7 fases (FASE 0 a FASE 6), ordenados por capítulo del TP (cap. 1 a 6).
- **Camino crítico** (11): `C-01 → C-02 → C-05 → C-06 → C-07 → C-13 → C-14 → C-16 → C-18 → C-19 → C-20`.
- **Primer change**: `C-01` (`foundation-setup`).
- **Fuera de alcance**: capítulo 7 (concurrencia avanzada) y capítulo 8 (colas Redis). No hay changes para ellos.

**Antes de cualquier `/opsx:propose`**: leé `CHANGES.md`, verificá que las dependencias estén archivadas y respetá los archivos de "Leer antes" de cada change.

---

## Reglas Duras

> Las reglas transversales de orquestación OPSX, governance por dominio, memoria (engram) y **Strict TDD** las inyecta el runtime del agente: el proyecto las **hereda**, no se repiten acá. (`~/.claude/CLAUDE.md` no existe en este entorno; si se crea, esta sección pasa a referenciarlo.)

Son contrato. Romperlas es un defecto:

1. **NUNCA** `HTTPException` con body ad-hoc → subclases de `AppError` (`NoAutenticadoError`, `ProhibidoError`, `NoEncontradoError`, `ConflictoError`, `ReglaNegocioError`, `DemasiadasPeticionesError`) mapeadas a `400/401/403/404/409/422/429` con body `{"detail", "codigo"}`.
2. **NUNCA** `commit()` en repositorios ni en handlers → solo `UnitOfWork.__aexit__` confirma o revierte; los repositorios hacen `flush()` y nunca cierran la sesión que no crearon.
3. **NUNCA** lazy loading implícito → relaciones con `lazy="raise"` y `selectinload` explícito en cada lectura de agregado (sin N+1).
4. **NUNCA** autorizar con los roles embebidos en el JWT → releer `asignacion_rol` vigentes (`revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`) en cada request protegida.
5. **NUNCA** ejecutar `bcrypt` dentro del event loop → `asyncio.to_thread` acotado por el `asyncio.Semaphore` creado en `lifespan`.
6. **NUNCA** handlers `def` sincrónicos → todos `async def`, sin I/O bloqueante en el loop.
7. **NUNCA** schema Pydantic sin `extra="forbid"` → los campos no declarados se rechazan con 422.
8. **NUNCA** `create_all` ni migraciones autogeneradas sin revisar → Alembic async; los `TRIGGERS` se escriben a mano en la migración.
9. **NUNCA** testear contra SQLite → tests contra PostgreSQL real (los índices únicos parciales, `CHECK` y triggers son load-bearing).
10. **NUNCA** introducir colas (`Celery`/Redis) → `BackgroundTasks` únicamente; el capítulo 8 está fuera de alcance.
11. **NUNCA** escribir en tablas de solo-agregado (`historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`) → los triggers de base de datos lo bloquean (RN-15).
12. **NUNCA** secretos ni DSN hardcodeados → `pydantic-settings` leyendo de variables de entorno / `.env`.
13. **NUNCA** código sin type hints ni identificadores fuera de `snake_case`.
14. **NUNCA** commitear ni buildear sin pedido explícito → conventional commits, sin co-autoría de IA en el mensaje.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y gates
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → TDD + reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.
