# Tasks

> Entorno de verificación: `DATABASE_URL=postgresql+asyncpg://postgres:postgres123@127.0.0.1:5433/taller_mecanico` y `JWT_SECRET=clave-secreta-de-prueba` exportados en la shell. Todos los tests nuevos viven en `tests/`; nunca en `test/`.

## 1. Preflight de seguridad (antes de tocar nada)

- [x] 1.1 Crear `scripts/verificar_tablas_vacias.py`: conecta con `DATABASE_URL`, recorre las 13 tablas de dominio y aborta con código de salida distinto de cero si alguna tiene `count(*) > 0`, listando las tablas infractoras. Verificar: `python scripts/verificar_tablas_vacias.py` termina con código 0 y reporta 0 filas en todas las tablas.
- [x] 1.2 Confirmar el punto de partida: `python -m alembic current` informa `003_solo_agregado (head)` y `python -m alembic check` falla con los 12 `modify_type` y el par `usuario_email_key`/`ix_usuario_email`. Verificar: salida registrada en la sesión de apply.
- [x] 1.3 (Opcional, recomendado) Generar backup previo: `pg_dump -h 127.0.0.1 -p 5433 -U postgres taller_mecanico > backup_pre_timestamptz.sql`. Verificar: el archivo existe y no está vacío (62,878 bytes; eliminado después de la verificación para no dejar un artefacto local).

## 2. Guarda de metadata (test first)

- [x] 2.1 Crear `tests/test_temporal_types.py::test_todas_las_columnas_datetime_son_timezone_aware`: recorre `SQLModel.metadata.tables`, resuelve `TypeDecorator.impl` cuando corresponda, y falla listando tabla/columna si alguna columna `DateTime` no tiene `timezone=True`. Verificar: `python -m pytest tests/test_temporal_types.py::test_todas_las_columnas_datetime_son_timezone_aware -v` pasa hoy (es una guarda a futuro) y falla si se agrega temporalmente un campo `datetime` sin `sa_type`.
- [x] 2.2 Cubrir el caso `UTCDateTime` en la guarda: verificar que `evento_seguridad.cuando` se inspecciona a través de su `impl` y no se omite por no ser instancia directa de `DateTime`. Verificar: el test de 2.1 incluye explícitamente `evento_seguridad.cuando` en el conjunto inspeccionado.

## 3. Tests de integración que reproducen el bug (test first, deben fallar)

- [x] 3.1 En `tests/test_temporal_types.py`, agregar `test_password_cambiada_en_roundtrip_preserva_instante_bajo_tz_no_utc`: con `test_db_session`, ejecutar `SET TIME ZONE 'America/Buenos_Aires'`, insertar un `Usuario` con `password_cambiada_en=2026-10-31T01:00:00+00:00`, releer por ORM y afirmar `tzinfo is not None` y `valor.astimezone(timezone.utc) == original`. Verificar: el test **falla** contra el esquema naive actual (relee `2026-10-30 22:00:00` sin tz).
- [x] 3.2 En el mismo archivo, agregar `test_evento_seguridad_cuando_roundtrip_aware_utc`: insertar un `EventoSeguridad`, releer `cuando` y afirmar timezone-aware y mismo instante (tolerancia 0, precisión de microsegundos). Verificar: el test **falla** contra el esquema naive actual.
- [x] 3.3 Crear `tests/test_auth_rn07_integracion.py::test_get_auth_yo_rechaza_token_anterior_a_password_cambiada_en_persistido` usando el fixture `contexto_auth`: `SET TIME ZONE 'America/Buenos_Aires'`, insertar `Usuario` con `password_cambiada_en` UTC aware, emitir token con `iat` 10 minutos antes, llamar `GET /auth/yo` con cookie y esperar `401`. Verificar: el test **falla** hoy (responde `200` porque el valor releído se interpreta como UTC y el `iat` queda después).
- [x] 3.4 Agregar `test_get_auth_yo_acepta_token_posterior_a_password_cambiada_en_persistido`: token con `iat` posterior al valor persistido → `200`. Verificar: el test pasa hoy y debe seguir pasando después del fix.
- [x] 3.5 Documentar en el docstring de ambos tests por qué se fuerza `SET TIME ZONE 'America/Buenos_Aires'` (determinismo aun en CI con `TimeZone=UTC`). Verificar: el docstring explica el corrimiento y el resultado esperado pre/post fix.

## 4. Correcciones de modelo

- [x] 4.1 En `app/modules/usuarios/models.py`, cambiar `EventoSeguridad.cuando` a `Field(nullable=False, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()})`. Verificar: `python -c "from sqlmodel import SQLModel; import app.modules.usuarios.models; print(SQLModel.metadata.tables['evento_seguridad'].c['cuando'].type)"` muestra `DateTime(timezone=True)`.
- [x] 4.2 En el mismo archivo, cambiar `Usuario.email` a `Field(unique=True, nullable=False)` eliminando `index=True`. Verificar: el metadata contiene `UniqueConstraint('email')` y ningún `Index` sobre `email`; `python -m pytest tests/test_auth_models.py::test_usuario_email_unico -v` sigue pasando.
- [x] 4.3 Auditar todos los campos `datetime` de `app/modules/clientes/models.py`, `app/modules/ordenes/models.py`, `app/modules/repuestos/models.py` y `app/modules/usuarios/models.py`; corregir cualquiera sin `DateTime(timezone=True)`. Verificar: `python -m pytest tests/test_temporal_types.py::test_todas_las_columnas_datetime_son_timezone_aware -v` pasa y el conjunto auditado son las 12 columnas temporales esperadas.
- [x] 4.4 Confirmar que **no** se creó ninguna revisión nueva: `git status --short migrations/versions` no muestra archivos `004_*`. Verificar: `python -m alembic heads` sigue mostrando sólo `003_solo_agregado`.

## 5. Reconstrucción del esquema de desarrollo (destructiva)

- [x] 5.1 Ejecutar **inmediatamente antes** del downgrade: `python scripts/verificar_tablas_vacias.py`. Si el script aborta (código ≠ 0), **DETENER** el change y no ejecutar 5.2; re-planificar con una revisión `004`. Verificar: código de salida 0 y 0 filas en las 13 tablas.
- [x] 5.2 `python -m alembic downgrade base`. Verificar: `information_schema.tables` no lista tablas de dominio (sólo `alembic_version`) y no quedan triggers/funciones `bloquear_modificacion_solo_agregado`.
- [x] 5.3 `python -m alembic upgrade head`. Verificar: las 12 columnas temporales figuran como `timestamp with time zone` en `information_schema.columns` y los 3 triggers de solo-agregado existen.
- [x] 5.4 `python -m alembic check`. Verificar: el comando termina con éxito y no reporta operaciones nuevas (sin `modify_type`, sin diferencia de constraint/índice de email).
- [x] 5.5 Re-ejecutar los tests del grupo 3: `python -m pytest tests/test_temporal_types.py tests/test_auth_rn07_integracion.py -v`. Verificar: los 4 tests pasan ahora.
- [x] 5.6 Verificar downgrades escalonados: `python -m alembic downgrade 002_dominio_taller`, `python -m alembic downgrade 001_auth_core`, `python -m alembic downgrade base`, y finalmente `python -m alembic upgrade head`. Verificar: cada paso termina sin error y la base vuelve a `head`; si algún `downgrade` falla, corregirlo dentro de este change y repetir.
- [x] 5.7 Registrar la regla de inmutabilidad de revisiones aplicadas en `knowledge-base/09_decisiones_y_supuestos.md` (decisión + razón: la causa raíz fue editar `001`/`002` post-aplicación; todo cambio futuro va en `004+`). Verificar: `Select-String -Path knowledge-base/09_decisiones_y_supuestos.md -Pattern "inmutable"` encuentra la decisión.

## 6. Verificación final e integración

- [x] 6.1 `python -m alembic upgrade head` (idempotente) y `python -m alembic check` en secuencia. Verificar: ambos exitosos, sin operaciones nuevas.
- [x] 6.2 `python -m pytest -v` completo. Verificar: 0 fallos nuevos respecto de la línea base; los tests nuevos de temporalidad y RN-07 aparecen en verde.
- [x] 6.3 Revisar el diff final: `git status --short` y `git diff --stat` muestran sólo modelos, tests, script de preflight y la nota de decisiones; ninguna revisión `004` ni edición a `001`/`002`/`003`. Verificar: revisión manual del diff.
- [x] 6.4 Confirmar la precondición de orden: anotar en el resumen del apply que este change quedó listo **antes** de C-11 `password-lifecycle`. Verificar: `CHANGES.md` sigue sin `[x]` en C-11.

## Workflow follow-up

- Archivar el change con `openspec-archive-change` una vez aprobada la verificación.
- Antes de iniciar C-11 `password-lifecycle`, confirmar que este change está archivado.
