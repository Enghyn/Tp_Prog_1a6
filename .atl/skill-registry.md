# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects the matching blocks directly into sub-agent prompts under `## Project Standards (auto-resolved)`. Sub-agents do NOT read this registry or individual `SKILL.md` files.

See `_shared/skill-resolver.md` for the full resolution protocol.

- **Project**: tp_prog — Taller Mecánico API (Python 3.12 + FastAPI + SQLModel + SQLAlchemy 2.0 async + PostgreSQL 16 + asyncpg + Alembic)
- **Generated**: 2026-10-26 by `skill-registry`
- **Sources of truth for scope**: `knowledge-base/` (11 files) and `CHANGES.md` (C-01…C-20, caps. 1-6)
- **Scope of this build**: 14 project skills in `.agents/skills/` (8 stack + 6 OpenSpec workflow). See appendix for session-level global skills that are listed but intentionally **not** expanded for delegation.

---

## Project-wide overrides (precedence over any individual skill block)

These are project decisions from `knowledge-base/` / `CHANGES.md`. When a generic skill recommends otherwise, **the override wins**; it must be injected alongside every block below.

- **Error contract**: raise the project's `AppError` subclasses (`ConflictoError`, `NoEncontradoError`, `ProhibidoError`, `NoAutenticadoError`, `ReglaNegocioError`, `DemasiadasPeticionesError`), never bare `HTTPException` with ad-hoc bodies. Handlers map to `400/401/403/404/409/422/429` with body `{"detail", "codigo"}` (C-02).
- **Transactions**: only `UnitOfWork.__aexit__` commits or rolls back. Repositories and `get_session()` **never** call `commit()` (C-13, C-14).
- **Lazy loading**: ORM relationships use `lazy="raise"`; every read of an aggregate uses explicit `selectinload`. No implicit N+1 (C-07, C-13, C-18).
- **Authorization**: roles packed in the JWT are informative only. Every request re-reads vigentes from `asignacion_rol` (`revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`) (C-10, RN-04).
- **Password hashing**: `bcrypt` 4.0 wrapped in `asyncio.to_thread`, bounded by an `asyncio.Semaphore` created in `lifespan`. Do **not** substitute `pwdlib`/Argon2, and do **not** prefer Asyncer over the documented `to_thread` approach (C-03, KB §09.4).
- **DB access**: SQLModel for table models, but raw SQLAlchemy 2.0 `select`/`selectinload` inside repositories. Async engine only (`postgresql+asyncpg`).
- **Tests run on PostgreSQL**, not SQLite: partial unique indexes, CHECK constraints and `BEFORE UPDATE/DELETE` triggers are load-bearing (C-05, C-06, C-07).
- **Background work**: FastAPI `BackgroundTasks` only. Celery/Redis/colas are explicitly out of scope (C-04, KB §10.2).

---

## Skills

| Skill | Trigger / when to use | Applies to | Path |
|-------|----------------------|------------|------|
| fastapi | FastAPI endpoints, Pydantic models, dependencies, response models, routing | ALL (C-01…C-20); core in C-02, C-09, C-10, C-15, C-16, C-18, C-19 | `.agents/skills/fastapi/SKILL.md` |
| fastapi-templates | Scaffolding/project layout, lifespan, layered router→service→repo, test fixtures | C-01, C-02, C-05, C-09, C-13, C-14, C-15, C-16, C-17, C-18, C-19 | `.agents/skills/fastapi-templates/SKILL.md` |
| auth-implementation-patterns | JWT login, cookie flags, bcrypt, RBAC, ownership checks, security auditing | C-09, C-10, C-11, C-12, C-17 | `.agents/skills/auth-implementation-patterns/SKILL.md` |
| async-python-patterns | asyncio, event loop safety, `to_thread`, semaphores, timeouts, async context managers | C-03, C-04, C-05, C-14, C-17, C-19 | `.agents/skills/async-python-patterns/SKILL.md` |
| python-testing-patterns | pytest fixtures, async tests, dependency overrides, DB tests, coverage | ALL (test suite per change); closing in C-20 | `.agents/skills/python-testing-patterns/SKILL.md` |
| postgresql-table-design | Postgres schema, data types, CHECKs, FKs, partial unique indexes, migrations | C-06, C-07, C-08, C-16 | `.agents/skills/postgresql-table-design/SKILL.md` |
| python-design-patterns | Layering, SRP, composition, DI, deciding when to abstract | C-13, C-14, C-15, C-16, C-17, C-18, C-19 | `.agents/skills/python-design-patterns/SKILL.md` |
| python-background-jobs | Decoupling work from the request cycle, `BackgroundTasks`, idempotency | C-04, C-19 | `.agents/skills/python-background-jobs/SKILL.md` |
| openspec-propose | Creating a change with proposal + specs + design + tasks | Every new change (C-01…C-20), proposal step | `.agents/skills/openspec-propose/SKILL.md` |
| openspec-apply-change | Implementing tasks from an existing change | Every change, implementation step | `.agents/skills/openspec-apply-change/SKILL.md` |
| openspec-archive-change | Closing an implemented change and promoting its specs | Every change, closure step | `.agents/skills/openspec-archive-change/SKILL.md` |
| openspec-sync-specs | Merging delta specs into main specs without archiving | Any change whose delta must reach `openspec/specs/` | `.agents/skills/openspec-sync-specs/SKILL.md` |
| openspec-update-change | Revising an existing change's artifacts coherently | Any change whose plan changes | `.agents/skills/openspec-update-change/SKILL.md` |
| openspec-explore | Thinking through a problem before/while planning, read-only | Before proposal or mid-change when requirements are unclear | `.agents/skills/openspec-explore/SKILL.md` |

---

## Compact Rules

### fastapi

- Declare parameters and dependencies with `Annotated`: `SessionDep = Annotated[AsyncSession, Depends(get_session)]`, then `session: SessionDep`. Create the alias once and reuse it.
- Never use `...` as the default for required params or model fields — omit the default instead.
- Declare the return type (`-> Page[RepuestoRead]`); use `response_model` only when the public schema differs from the internal return value.
- Do not use `ORJSONResponse`/`UJSONResponse` (deprecated) and do not use Pydantic `RootModel`; use `Annotated[list[X], Field(...), Body()]`.
- Put `prefix`, `tags` and shared `dependencies=[Depends(...)]` on the `APIRouter`, not in `include_router()`.
- One HTTP operation per function; never branch inside one handler over GET/POST.
- Declare `async def` only if everything inside is awaited and non-blocking; otherwise use plain `def` (threadpool). Never call bcrypt, `time.sleep`, or sync drivers inside an async handler.
- Use dependencies for anything depending on external resources or needing `yield` cleanup; not for logic that fits Pydantic validation.
- **Override**: do not raise `HTTPException` for domain failures — raise the `AppError` subclass so C-02 handlers produce the uniform body and code.
- Every request schema declares `model_config = ConfigDict(extra="forbid")`; strings are stripped, emails use `EmailStr`.
- Response schemas never expose `password_hash`; return types are what enforce that filter.

### fastapi-templates

- Layering is `router.py → service.py → repository.py → models`; the router does HTTP only, the service holds business rules, the repository holds queries.
- **Override layout**: use `app/core/` + `app/modules/{health,usuarios,clientes,repuestos,ordenes}/` per KB §02, not the template's `app/api/v1/endpoints/` tree.
- `lifespan` owns the async engine, the `async_sessionmaker` and the bcrypt `Semaphore`, stored on `app.state`; `await engine.dispose()` on shutdown.
- `get_session()` yields exactly one `AsyncSession` per request inside `async with`, guaranteed close, and **no commit**.
- Use `async_sessionmaker(..., expire_on_commit=False)` so objects stay usable after the UoW commits.
- `BaseRepository[T]`: `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `add`/`update` do `flush()`, never `commit()`.
- Keep SQLModel table models separate from request/response schemas; never return a table model directly.
- Register error handlers once in `create_app()`; routers do not wrap each other's exceptions.
- Tests: `@pytest_asyncio.fixture` (strict mode), `ASGITransport(app=app)` because httpx 0.28 dropped `AsyncClient(app=...)`, and always `app.dependency_overrides.clear()` in teardown.
- **Override**: the test DB is PostgreSQL (ephemeral schema/transaction rollback), not the template's `sqlite+aiosqlite` — the schema relies on partial indexes and triggers.

### auth-implementation-patterns

- Hash with bcrypt only; never store, log or return plaintext or `password_hash`.
- Verify unknown emails against a precomputed dummy hash with the same code path and timing (RN-09); the response must be identical to a wrong password.
- Issue the JWT in an `HttpOnly` cookie — never localStorage, never a JS-readable cookie. Flags: `HttpOnly`, `SameSite=Lax`, `secure` by environment, `max_age = TTL`.
- Keep access tokens short (15-30 min), sign HS256 with `sub`, `iat`, `exp`; `roles` is informational and must never be the authorization source.
- Authorize server-side on every request from DB state (`asignacion_rol` vigente); a revoked role loses access on the very next request.
- Distinguish `401` (no/invalid credential) from `403` (authenticated but not allowed); do not leak whether the email exists.
- Rate-limit login by `(email, ip)` within the window and return `429` + `Retry-After` **before** computing any hash.
- Check resource ownership server-side for `/mis-*` endpoints (RN-17); never trust a client-supplied owner id.
- Invalidate sessions by rejecting tokens whose `iat` is earlier than `password_cambiada_en`, comparing with microsecond precision (RN-07).
- Record `evento_seguridad` for login ok/fail/blocked, logout, password change and role changes; never log tokens or passwords.
- **Override**: bcrypt runs through `asyncio.to_thread` + `Semaphore`; skip the skill's generic async-framework and OAuth2/SSO sections (out of scope).

### async-python-patterns

- Never block the loop: no `time.sleep`, no sync DB/HTTP drivers, no CPU-heavy work inside `async def`.
- Keep a call path fully sync or fully async; do not mix styles in the same handler/service.
- Offload blocking work with `await asyncio.to_thread(fn, ...)`; bound it with `asyncio.Semaphore` (bcrypt: one shared semaphore from `lifespan`).
- Wrap external calls and the readiness probe with `asyncio.wait_for(..., timeout=...)`; never wait indefinitely.
- Use `asyncio.gather(*tasks, return_exceptions=True)` when one failure must not cancel the rest.
- Always `await` coroutines; if you must background something, keep the task reference to avoid silent GC.
- On `asyncio.CancelledError`, clean up and re-raise — never swallow it.
- Manage sessions/engine with `async with`; a leaked `AsyncSession` is a leaked connection.
- Concurrency control belongs in the event loop, not in threads (`Lock`/`Semaphore`), so state stays consistent across requests.
- Tests: `@pytest.mark.asyncio` + pytest-asyncio; include a "loop stays responsive" test that measures a trivial endpoint while bcrypt load runs.

### python-testing-patterns

- Arrange-Act-Assert, one behavior per test, name `test_<unit>_<scenario>_<expected>`.
- Tests are independent: no shared mutable state; fixtures own setup **and** teardown.
- Per-test isolation for DB tests: outer transaction + rollback, or a fresh schema; never rely on ordering.
- Async tests need `@pytest.mark.asyncio` and `pytest_asyncio.fixture`; configure `asyncio_mode` explicitly instead of implicit auto mode.
- Override `get_session`/`get_uow` through `app.dependency_overrides` and clear them in teardown.
- Mock only boundaries (external notifier, clock, network); never mock the repository you are supposed to be testing.
- Use `side_effect` lists to exercise retry/error sequences and assert call counts.
- Use `pytest.raises` for expected domain errors and `freeze_time` for TTL/`exp`/`iat`; never `sleep` to test time.
- **Override**: PG-specific behavior (partial unique index → `IntegrityError` → 409, CHECK constraints, sólo-agregado triggers) must be tested against real PostgreSQL.
- Mark `slow`/`integration`; the default suite stays fast and green.
- Coverage is a smell detector, not a goal: every RN-01…RN-20 needs at least one test that actually exercises it (C-20).

### postgresql-table-design

- `snake_case`, unquoted identifiers; primary keys `BIGINT GENERATED ALWAYS AS IDENTITY` (never `serial`).
- Time is `TIMESTAMPTZ` (never `timestamp`/`timetz`); money is `NUMERIC(p,s)` (never `money`, never float); strings are `TEXT` with `CHECK (length(...))` when bounded (never `varchar(n)`/`char(n)`).
- `NOT NULL` wherever semantically required, plus sensible `DEFAULT`s; a `CHECK` alone passes on NULL, so pair every CHECK with NOT NULL.
- Encode invariants as CHECKs where the value set is stable: `anio BETWEEN 1950 AND 2100`, `precio > 0`, `stock >= 0`, `cantidad <> 0`, `total >= 0`.
- **FK columns are not auto-indexed** — add an explicit index for every FK used in joins/filters, and declare `ON DELETE`/`ON UPDATE` explicitly.
- Logical delete needs a **partial unique index**, not a plain UNIQUE: `CREATE UNIQUE INDEX uq_x_vigente ON x (col) WHERE borrado_en IS NULL`.
- Same rule for open rows: `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL` (RN-03).
- A plain `UNIQUE` allows many NULLs; use `UNIQUE NULLS NOT DISTINCT` (PG15+) only when a single NULL is intended.
- Enums: use `TEXT` + `CHECK` (roles) or a lookup table (`estado_orden`) — do not create PG `ENUM` for evolving business values.
- Name every constraint and index explicitly in migrations so `IntegrityError` mapping and downgrades are predictable.
- Migrations: one logical change per revision, reversible, hand-reviewed for indexes/CHECKs/triggers; verify `upgrade head` **and** `downgrade base`.
- No partitioning, JSONB or RLS at this scale; do not add them speculatively.

### python-design-patterns

- Dependency direction is API → Service → Repository; services never import routers, HTTP types or `Request`.
- Give each class one reason to change; if it parses HTTP **and** enforces business rules **and** builds queries, split it.
- Compose, don't inherit: shallow trees (2-3 levels), narrow `Protocol` seams (`NotificadorCliente`), no decorator towers.
- Constructor injection for session/UoW/repositories; if a constructor needs 7+ params, the class has too many responsibilities.
- Apply the rule of three before abstracting; delete dead code first; duplication beats a premature abstraction.
- Keep functions 20-50 lines with one purpose; explicit and boring beats clever.
- The UoW owns the transaction boundary; services orchestrate, repositories query and `flush()`, nobody else commits.
- Do not leak ORM models past the service boundary when a schema is the public contract.
- Testability is the design signal: if a unit needs a live DB to test a business rule, move the I/O behind an injected collaborator.

### python-background-jobs

- Keep the request path short: schedule in-process `BackgroundTasks` for the client notification (C-04); Celery/Redis/colas are out of scope.
- Enqueue **after** `uow.commit()`; scheduling before the commit can notify about work that rolled back.
- Never pass `AsyncSession`, `Request`, or ORM objects into the task — pass plain values (`orden_id`, `email`, `total`).
- The task swallows and logs its own exceptions; a task failure must never change the `200` already sent.
- Background code must not reuse a closed session; if it ever needs DB access, it opens its own session/UoW.
- Assume at-least-once: make effects idempotent. Assume loss is possible without a queue — document it in `10_preguntas_abiertas.md`.
- Log task start/end with the order id and no PII beyond what the flow needs.
- If a real queue is introduced later: persist job state, exponential backoff for transient errors, no retry on permanent errors, hard/soft timeouts, DLQ, queue-depth monitoring.

### openspec-propose

- Planning only: create `proposal.md`, delta `specs/<capability>/spec.md`, optional `design.md`, and `tasks.md`. Do **not** edit project code, and do not start apply in the same turn.
- Run `openspec context --json` first; a `root: null` means "not set up" — stop, and only offer `openspec init` on an explicit OpenSpec request.
- Create the change with `openspec new change "<kebab-case-name>"`; never hand-create the directory. In this project use roadmap names (`C-01-foundation-setup`, …).
- Drive artifact order from `openspec status --change "<name>" --json` (`applyRequires` + transitive `requires`), not from assumptions.
- For each artifact, read `openspec instructions <artifact-id> --change "<name>" --json` and follow its `instruction`/`template` — they outrank your habits.
- Always re-read dependency artifacts from disk before writing the next one.
- `context` and `rules` are constraints for you; never copy them into the artifact.
- Inspect real code/tests/config read-only before drafting scope and tasks; surface conflicts with existing specs instead of silently choosing.
- Keep the change atomic (~4-6 h, one capability slice); cross-reference its "Leer antes" KB docs.
- Stop only when every transitively required artifact is `done` or legitimately `skipped`, then hand off to apply.

### openspec-apply-change

- Implement only what the change's tasks/specs say; announce `Using change: <name>` and how to override it.
- Run `openspec status --change "<name>" --json`, then `openspec instructions apply --change "<name>" --json`, and read **every** path in `contextFiles`.
- If `state: "blocked"`, do not implement: complete the missing artifacts first (`status` → next `ready` → `instructions`).
- Work one task at a time, keep edits minimal and focused; do not refactor unrelated code.
- Before ticking, verify the checkbox at the returned `sourcePath`/`line` still matches; then `- [ ]` → `- [x]` and re-run apply instructions to confirm progress advanced.
- Pause and ask when the task is unclear, a design issue appears, or the work grows beyond the spec — never silently narrow or drop specified behavior.
- Do not commit, archive, or update `CHANGES.md` unless the user/orchestrator asks.
- If `state: "all_done"`, stop and suggest archive.
- Apply the injected project standards over generic skill defaults.

### openspec-archive-change

- Archive only after implementation; announce `Using change: <name>`.
- Check `openspec status --json`; list incomplete artifacts and ask for confirmation before proceeding.
- Count tasks from `openspec list --json` (`totalTasks` / `completedTasks`); only `x`/`X` count as complete. Never infer completion from artifact status.
- Evaluate delta specs vs main specs; choose "Sync now", "Archive without syncing", or "Cancel" — never sync while a capability is sync-blocked.
- Archive via `openspec archive`, into the path derived from `planningHome.changesDir`; never move directories by hand.
- Verify the sync result afterwards; report specs synced, skipped, or delta-less.
- Do not delete or rewrite the change's artifacts; archiving moves them.
- Report the final progress (`N/M tasks`) and the spec sync outcome.

### openspec-sync-specs

- Delta sections are `ADDED`, `MODIFIED`, `REMOVED`, `RENAMED` (FROM:/TO:); merge intelligently, preserving scenarios the delta does not mention.
- Source of delta paths is **only** `artifactPaths.specs.existingOutputPaths`; resolve main specs under `planningHome.root/openspec/specs/<capability-path>/spec.md`.
- Fetch `openspec instructions specs --change "<name>" --json` once before the first main-spec write; its `rules` constrain form, not scope.
- A missing main spec is a new capability: only `ADDED` can build it; `MODIFIED`/`RENAMED` → sync-blocked, never invent the requirement.
- `ADDED` that already exists is an implicit `MODIFIED` — update it rather than duplicating the block.
- `REMOVED` retires a capability only when no requirement blocks remain and `.openspec.yaml` declares `retire_capabilities: true`; never leave an empty `## Requirements`.
- Preserve the `## Purpose` and untouched sections; change only what the delta names.
- If a caller narrowed the delta list, sync exactly those paths — never widen back to the full list, never silently drop one.
- Stop and report when a path is missing or a capability is blocked; do not write a partial main spec.

### openspec-update-change

- Planning artifacts only — never edit implementation code; if the plan implies code, point to `/openspec-apply-change`.
- Do not create missing artifacts (except a confirmed concrete path inside an already-populated glob artifact); that is the propose/continue workflow.
- Read all existing artifacts, then reconcile in **any** direction: a change to a later artifact may require revising an earlier one.
- Edit only `artifactPaths.<id>.existingOutputPaths`; never write to a glob `resolvedOutputPath`.
- Draft edits in conversation, show every proposed revision with its reason, and write only after explicit user confirmation — one artifact at a time.
- Leave `skipped` artifacts untouched; do not treat them as missing.
- If the request changes the change's **intent**, recommend a new change name via `openspec new change` instead of rewriting this one.
- Never advance the build frontier; finish by naming the next command (`apply` or `archive`).

### openspec-explore

- Thinking partner, not implementer: read files, search, run read-only commands, but never write code, schemas, templates or `openspec/config.yaml`.
- Design/clarifying answers are never permission to write. Before the first write-capable action, name the exact files and change, ask a direct yes/no question, and wait for a separate message.
- Creating/updating change artifacts is allowed only within that confirmed scope; expanding the scope requires a new confirmation.
- Never hand-scaffold: use `openspec new change "<name>"`; no manual `openspec/changes/` directories.
- Ground the discussion in the actual codebase and KB; question assumptions, including the user's and your own.
- Diagrams: plain ASCII only (`+ - |`, `-->`, `*`, `x`) — no unicode box drawing.
- Offer to capture insights; do not auto-capture. Hand off to `/openspec-propose` when the thinking is ready to become a change.
- No fixed steps and no mandatory output; a summary (`problem`, `approach`, `open questions`, `next steps`) is optional.

---

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| — | — | **None yet.** `CLAUDE.md` / `AGENTS.md` / `.cursorrules` do not exist; they are generated later by the `agent-instruction` phase. |

Do not invent conventions here. Until `AGENTS.md`/`CLAUDE.md` exist, the only authoritative project material is:

| Document | Path | Role |
|----------|------|------|
| Knowledge base | `knowledge-base/01_vision_y_objetivos.md` … `10_preguntas_abiertas.md` | Domain, data model, business rules RN-01…RN-20, architecture |
| Change roadmap | `CHANGES.md` | 20 atomic changes, dependency gates, per-change "Leer antes" |

---

## Appendix — Session-level global skills (listed, not expanded)

These live under `~/.config/opencode/skills/` and belong to the foundation/orchestration flow, not to implementation sub-agents. Do not inject them into C-01…C-20 sub-agent prompts. Listed for completeness so no delegator wastes time re-scanning.

| Skill | Purpose | Path |
|-------|---------|------|
| active-orchestrator | Runs the project foundation flow and owns `.active-orchestrator-state.json` | `~/.config/opencode/skills/active-orchestrator/SKILL.md` |
| discovery-research | Market/requirements discovery before the KB | `~/.config/opencode/skills/discovery-research/SKILL.md` |
| kb-creator | Builds `knowledge-base/` (10 canonical files) | `~/.config/opencode/skills/kb-creator/SKILL.md` |
| roadmap-generator | Generates `CHANGES.md` | `~/.config/opencode/skills/roadmap-generator/SKILL.md` |
| agent-instruction | Generates `AGENTS.md` / `CLAUDE.md` (next phase) | `~/.config/opencode/skills/agent-instruction/SKILL.md` |
| find-skill | Discovers/installs skills | `~/.config/opencode/skills/find-skill/SKILL.md` |
| skill-creator | Authors/edits skills | `~/.config/opencode/skills/skill-creator/SKILL.md` |
| web-scraper | Competitor research from a URL | `~/.config/opencode/skills/web-scraper/SKILL.md` |
| skill-registry | This registry generator (never delegate) | `~/.config/opencode/skills/skill-registry/SKILL.md` |
