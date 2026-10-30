# Design

## Context

El sistema ya cuenta con motor async (SQLAlchemy 2.0 + asyncpg), sesión sin auto-commit (`get_session`), y scaffolding de Alembic async (C-05). Este change introduce los primeros modelos SQLModel con `table=True` y la primera migración real. Ver proposal.md para motivación.

Constraints relevantes:
- Reglas duras #3 (`lazy="raise"`), #8 (Alembic, no `create_all`), #9 (tests contra PostgreSQL real), #13 (type hints + snake_case).
- RN-01 (unicidad email), RN-03 (un rol abierto por tipo), RN-05 (autoprotección admin — fuera de alcance de este change, se implementa en servicio).

## Goals / Non-Goals

**Goals:**
- Definir los 4 modelos SQLModel con todas las constraints de la KB
- Crear migración Alembic `001_auth_core` revisada a mano con índice único parcial y compuesto
- Validar integridad de datos con tests contra PostgreSQL real

**Non-Goals:**
- Endpoints de auth (C-08, C-09)
- Repositorios / Unit of Work para estas tablas (C-08)
- Lógica de negocio de RN-05 (autoprotección admin — se implementa en servicio, no en modelo)
- Seeds de datos iniciales (se hará en change posterior)

## Decisions

### D1: SQLModel con `table=True` vs SQLAlchemy puro
**Decisión**: SQLModel con `table=True` para los modelos.
**Rationale**: El stack del proyecto define SQLModel como ORM (KB-02). SQLModel unifica modelo de datos y schema Pydantic. Las constraints complejas (CHECK, índice parcial) se declaran via `sa_column` y `__table_args__`.
**Alternativa descartada**: SQLAlchemy `DeclarativeBase` puro — no aprovecharía la integración Pydantic que el proyecto requiere.

### D2: CHECK constraint de rol como tupla en `__table_args__`
**Decisión**: Declarar el CHECK de rol (`ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`) como `sa.CheckConstraint` en `__table_args__` de `AsignacionRol`, usando una constante `ROLES_VALIDOS` reutilizable.
**Rationale**: PostgreSQL enforza el CHECK a nivel de DB — la validación es inviolable independientemente del punto de entrada. La constante centraliza los valores para reusar en validaciones Python.
**Alternativa descartada**: Enum de PostgreSQL — más rígido para agregar roles futuros (requiere `ALTER TYPE`).

### D3: Índice único parcial via `Index` en `__table_args__`
**Decisión**: `sa.Index("uq_asignacion_rol_abierta", "usuario_id", "rol", unique=True, postgresql_where=text("revocada_en IS NULL"))`.
**Rationale**: Esto garantiza RN-03 a nivel de DB. El índice parcial es la solución estándar de PostgreSQL para "a lo sumo uno abierto". Los tests DEBEN correr contra PostgreSQL (regla #9) porque SQLite no soporta índices parciales.

### D4: Índice compuesto en `intento_acceso`
**Decisión**: `sa.Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando")`.
**Rationale**: Soporta la consulta de RN-08 (5 fallos en 60s por email+IP) sin full table scan. El orden de columnas `(email, ip, cuando)` coincide con el patrón de filtrado `WHERE email = ? AND ip = ? AND cuando > ?`.

### D5: Migración escrita a mano vs autogenerada
**Decisión**: Generar con `alembic revision --autogenerate` y luego **revisar y editar** a mano.
**Rationale**: Alembic autogenerate no detecta índices parciales con `postgresql_where` ni CHECK constraints de forma confiable. La migración final DEBE incluir ambos explícitamente. Regla dura #8 exige revisión.

### D6: Relaciones con `Relationship` de SQLModel
**Decisión**: Usar `Relationship(back_populates=..., sa_relationship_kwargs={"lazy": "raise"})` en ambos lados.
**Rationale**: Regla dura #3 exige `lazy="raise"`. SQLModel envuelve `relationship()` de SQLAlchemy; pasamos `lazy` via `sa_relationship_kwargs` ya que SQLModel no expone `lazy` directamente.

### D7: Ubicación de modelos
**Decisión**: `app/modules/usuarios/models.py` para los 4 modelos.
**Rationale**: Siguen la estructura de 6 capas del proyecto (KB-02). Las 4 tablas pertenecen al dominio de identidad/auth, que vive bajo el módulo `usuarios`.

## Risks / Trade-offs

- **[Riesgo] PostgreSQL no disponible para tests** → Los tests de integridad usan `pytest.skip()` si la conexión falla. El CI debe garantizar PostgreSQL disponible.
- **[Riesgo] Autogenerate de Alembic no detecta todo** → Mitigación: revisar la migración generada y agregar manualmente el índice parcial y el CHECK si no aparecen.
- **[Trade-off] CHECK string vs Enum de PG** → Más flexible para agregar roles (simple `ALTER TABLE ... DROP/ADD CONSTRAINT`) pero sin validación de tipo a nivel de PG. Aceptable para 4 roles estáticos.

## Migration Plan

1. Crear modelos en `app/modules/usuarios/models.py`
2. Importar modelos en `migrations/env.py` para que Alembic detecte el metadata
3. Ejecutar `alembic revision --autogenerate -m "001_auth_core"`
4. Revisar y editar la migración: verificar CHECK, índice parcial, índice compuesto
5. Ejecutar `alembic upgrade head` para validar
6. Ejecutar `alembic downgrade base` para validar reversibilidad
7. **Rollback**: `alembic downgrade base` elimina las 4 tablas limpiamente

## UI Mockups

Decision: no (no UI)
