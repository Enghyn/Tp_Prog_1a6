# 08 - Arquitectura Propuesta y Patrones de Diseño

## Arquitectura en Capas
Cada módulo funcional implementa estrictamente 6 capas:
`Router` → `Service` → `UoW` → `Repository` → `Model`

1. **Router (`router.py`)**: Endpoints HTTP FastAPI (`async def`). Construyen el Unit of Work mediante dependencias y delegan en el servicio. Traducen excepciones de negocio a códigos HTTP precisos.
2. **Service (`service.py`)**: Contiene toda la lógica de negocio y reglas (RN-01 a RN-20). Abre el `UnitOfWork` mediante `async with`.
3. **Unit of Work (`unit_of_work.py`)**: Gestor de contexto asincrónico que agrupa repositorios bajo una misma sesión de base de datos. Confirma (`commit`) al salir exitosamente del bloque, o revierte (`rollback`) si ocurre una excepción. **No cierra la sesión**, ya que no la creó.
4. **Repository (`repository.py`)**:
   - `BaseRepository[T]`: Ofrece operaciones genéricas (`get_by_id`, `get_all`, `count`, `add`, `update`, `delete`). Los métodos `add` y `update` ejecutan `flush()`, **nunca `commit()`**.
   - `SoftDeleteRepository[T]`: Hereda del base, filtra registros dados de baja (`borrado_en IS NULL`) y añade `get_by_id_including_deleted` y `soft_delete`.
   - Toda relación leída se precarga explícitamente en el repositorio (evitando N+1 y carga perezosa).
5. **Model (`models.py`)**: Modelos SQLModel con definición de tablas, restricciones (`CHECK`, `UNIQUE`, índices parciales) y relaciones bidireccionales.

## Ciclo de Vida (`main.py` y `database.py`)
- El motor asincrónico de SQLAlchemy y la fábrica de sesiones (`async_sessionmaker`) se crean en el evento `lifespan` de la aplicación y se almacenan en `app.state`.
- `get_session` obtiene la fábrica desde `app.state`, entrega una sesión por petición configurada con `expire_on_commit=False`, y la cierra al finalizar.
- Al apagar el servidor, el `lifespan` ejecuta `motor.dispose()`.
