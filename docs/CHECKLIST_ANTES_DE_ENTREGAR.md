# Checklist antes de entregar

> Versión corta y ejecutable de `docs/LECCIONES_APRENDIDAS.md`.
> Copiar al repo del próximo TP y correr **en una carpeta limpia**, con la versión de Python y
> PostgreSQL de la cátedra. Si un ítem falla, no se entrega.

## 0. Reglas que no se negocian

- [ ] La implementación vive en el path exacto de la consigna (`app/core/config.py`,
  `app/core/security.py`, `test/solo_agregado.sql`, `env.example`). Sin shims.
- [ ] Ninguna credencial en `alembic.ini`, `env.example`, README ni código.
- [ ] El router construye el UoW; el servicio lo abre; solo `__aexit__` confirma.
- [ ] Ningún `selectinload` fuera de `repository.py`.
- [ ] Ninguna regla de negocio que no esté en la consigna.

## 1. Estructura

- [ ] `main.py` con `lifespan` y los dos grupos de rutas (público / protegido).
- [ ] `seed.py` en la raíz.
- [ ] `app/core/`: `config.py`, `database.py`, `security.py`, `dependencies.py`,
  `repository.py`, `paginacion.py`, `unit_of_work.py`.
- [ ] `app/modules/{health,usuarios,clientes,repuestos,ordenes}/` con las seis capas.
- [ ] `health` solo tiene `router.py`.
- [ ] `migrations/` con Alembic.
- [ ] `test/` con `.http` por módulo y `solo_agregado.sql`.
- [ ] `tests/` solo pytest; nada de `.http` ni `.sql` sueltos.
- [ ] `env.example` (sin punto inicial) y `.gitignore` con `.env`.

## 2. Configuración

- [ ] `Settings` con `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`,
  `POSTGRES_PORT`, `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`,
  `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`, `POOL_SIZE`.
- [ ] `@computed_field` que arma la URL con driver async.
- [ ] `JWT_SECRET` obligatorio, sin default; la app no arranca si falta.
- [ ] `alembic.ini` sin `sqlalchemy.url` con credenciales; `migrations/env.py` lee de `Settings`.
- [ ] `get_session` lee el `sessionmaker` de `app.state`, no de un global.
- [ ] Motor y `sessionmaker` creados **solo** en `lifespan`; `dispose()` al apagar.

## 3. Modelo y migraciones

- [ ] Nombres de tablas y columnas exactos de la consigna.
- [ ] `UNIQUE` e índices únicos parciales para borrado lógico.
- [ ] `CHECK` de dominio (año, precios, stock, cantidades, total).
- [ ] Navegación uno-a-uno `Usuario.cliente` y su inversa.
- [ ] Índice en **cada** FK (verificar con la query del Anexo A).
- [ ] Migración autogenerada con comentario: qué se revisó y qué se cambió a mano.
- [ ] Migración manual de triggers de solo-agregado.
- [ ] `alembic upgrade head` / `downgrade base` / `upgrade head` sin error.
- [ ] `alembic check` sin operaciones nuevas.

## 4. Contratos y CRUD

- [ ] Un schema por operación (`Create`, `Update`, `Read`), con `extra="forbid"`.
- [ ] Campos de más rechazados con 422.
- [ ] Códigos: 404 → 403 → 409 → 422, en ese orden.
- [ ] PATCH parcial: solo modifica lo enviado; `null` explícito según contrato.
- [ ] Paginación: `{items,total,page,size,pages}`, `page` desde 1, `size` 1..100 default **20**,
  página fuera de rango **422**, cero resultados **una página vacía**.
- [ ] `total` cuenta con los mismos filtros que la página.
- [ ] Búsqueda con parámetros ligados (nunca concatenación).

## 5. Autenticación

- [ ] bcrypt con `rounds` desde `Settings`; `to_thread` + semáforo.
- [ ] Límite de 72 bytes en el contrato → **422**.
- [ ] Login: primero rate limit (429 con `Retry-After`), después verificación.
- [ ] Mismo mensaje y mismo tiempo con correo existente/inexistente (hash ficticio).
- [ ] `iat` y `exp` numéricos (NumericDate); comparar con `password_cambiada_en` sin truncar.
- [ ] Cookie `access_token`: `HttpOnly`, `SameSite=Lax`, `Max-Age`, `Secure` según entorno.
- [ ] El token nunca viaja en el body ni se lee de `Authorization`.
- [ ] Login devuelve `debe_cambiar_password` en el **nivel superior**.
- [ ] `/auth/cambiar-password` **entrega cookie nueva**; la anterior da 401.
- [ ] Gating de RN-06 por grupo de rutas (`/auth/*` y `/health/*` exentas).

## 6. Autorización

- [ ] Roles vigentes releídos de `asignacion_rol` en cada request.
- [ ] `require_rol` como dependencia, no dentro del handler.
- [ ] Permiso **antes** que estado (403 antes que 409).
- [ ] Reglas de recurso en el servicio: mecánico asignado, dueño del vehículo.
- [ ] Autoprotección de ADMIN y «nunca sin administradores».
- [ ] `/mis-*` solo con sesión; dueño estricto; 403 si no es propio.

## 7. Repositorios y Unit of Work

- [ ] `BaseRepository[T]` y `SoftDeleteRepository[T]` separados.
- [ ] El repositorio conoce su clase de modelo.
- [ ] Ningún repositorio hace `commit()`; solo `flush()`.
- [ ] Toda precarga vive en el repositorio.
- [ ] El UoW base confirma/revierte en `__aexit__` y no cierra la sesión.
- [ ] El router construye el UoW; el servicio lo abre; ningún servicio lo construye.
- [ ] Operaciones de varias escrituras: todas dentro del mismo `async with uow`.

## 8. Reglas de negocio críticas

- [ ] Crear orden: PENDIENTE, al menos un ítem, sin repuestos repetidos, precio copiado, total
  calculado, **historial inicial**.
- [ ] Terminar: descuenta stock, deja un movimiento por ítem y una línea de historial; si falta
  stock, **nada** queda escrito.
- [ ] Cancelar: recepción, admin o dueño; permiso antes que estado; solo desde PENDIENTE.
- [ ] Iniciar: solo mecánico; queda asignado; PENDIENTE → EN_REPARACION.
- [ ] Stock: un único punto de escritura; alta, reposición y terminación dejan movimiento.
- [ ] Precio: cada cambio deja historial en la misma transacción; sin cambio, sin línea.
- [ ] Vehículo/repuesto dado de baja: no se usa en órdenes nuevas; no se da de baja con órdenes
  abiertas.
- [ ] Solo-agregado: triggers bloquean UPDATE y DELETE en las tres tablas.

## 9. Seed

- [ ] Corre después de `alembic upgrade head`, sin error, y es idempotente.
- [ ] Carga el catálogo de estados **primero**.
- [ ] Carga exactamente los usuarios de la consigna (incluidos `admin2`, `mecanico2`, `nuevo`).
- [ ] Carga Laura (con usuario y dos vehículos) y Jorge (sin usuario, un vehículo).
- [ ] Carga filtro (10), pastillas (4), bujía (2) y aceite (20), con movimiento «Stock inicial».
- [ ] Carga la orden 1 (PENDIENTE) y la 2 (EN_REPARACION, asignada, con 4 bujías).
- [ ] Carga historial de precio 8000 → 8500 y evento `SISTEMA`.
- [ ] Un test afirma estos valores leyendo la base.

## 10. Tests

- [ ] Un test por cada caso `C-NN`, contra HTTP (`TestClient`/`httpx`), con el seed oficial.
- [ ] Los tests comparan **status + body**, no `model_dump()`.
- [ ] Tests contra PostgreSQL real (nunca SQLite).
- [ ] Tests de FK sin índice, de navegación y de triggers.
- [ ] Tests de entradas extremas: id enorme, cantidad enorme, NUL, `q` con NUL, JSON malformado.
- [ ] `pytest` completo en verde.

## 11. Paquete final

- [ ] Sin `.env`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.venv`, tooling local.
- [ ] `requirements.txt`, `env.example`, `alembic.ini`, `migrations/`, `test/`, `tests/`,
  `seed.py`, `main.py`, `README.md`.
- [ ] README con integrantes, comisión, instalación, migraciones, seed, tests y ejecución.
- [ ] Zip generado desde el commit final.
- [ ] `git status` limpio y `HEAD == origin/main`.

## 12. Frase de cierre

> Si un caso de la consigna no se corrió literalmente, no está verificado.
> Si un test no abrió el JSON real, no está verificado.
> Si no se corrió en una carpeta limpia, no está verificado.
