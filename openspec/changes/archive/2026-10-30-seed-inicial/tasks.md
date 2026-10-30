# Tasks

## 1. Reubicar la suite pytest y fijar la convención de carpetas

- [x] 1.1 Red de seguridad: ejecutar la suite actual (`pytest test/`) sobre PostgreSQL real y registrar el resultado base (pasados, omitidos y fallos preexistentes). Verificación: informe con el conteo base; si hay fallos preexistentes se reportan sin corregirlos en este change.
- [x] 1.2 Mover `test/conftest.py`, `test/__init__.py` y los diez `test_*.py` a `tests/` sin cambiar su contenido, y agregar `pytest.ini` con `testpaths = tests`, `asyncio_mode = strict` y `pythonpath = .`. Verificación: `pytest` desde la raíz descubre `tests/` y el resultado coincide con la línea base de 1.1.
- [x] 1.3 Verificar que `test/` ya no contiene archivos `.py` y que conserva `salud.http`. Verificación: `Get-ChildItem test -Filter *.py` no devuelve resultados y `salud.http` sigue presente.
- [x] 1.4 Actualizar el comentario de cabecera de `scripts/verificar_solo_agregado.sql` (movido desde `test/solo_agregado.sql`) con la nueva ruta de invocación. Verificación: el archivo existe en `scripts/` y `rg "test/solo_agregado"` no lo encuentra.

## 2. Esqueleto del seed y catálogo `estado_orden`

- [x] 2.1 RED: crear `tests/test_seed.py` con casos que exijan el catálogo canónico (4 filas, posiciones 1–4, `es_final` correcto) y que una segunda ejecución no duplique ni derive valores. Verificación: los tests fallan porque `seed.py` no existe o no carga el catálogo.
- [x] 2.2 GREEN: implementar `seed.py` con parseo de argumentos (`--reset`, `--si`, `--forzar`), guardia de entorno, motor/sesión async, una única transacción y carga convergente del catálogo. Verificación: los tests de 2.1 pasan.
- [x] 2.3 TRIANGULATE: agregar un caso con una fila de catálogo alterada y otro con la tabla ya completa; implementar la convergencia mínima. Verificación: todos los casos del catálogo pasan tras dos ejecuciones consecutivas.
- [x] 2.4 REFACTOR: extraer constantes de datos y helpers de búsqueda/inserción sin cambiar comportamiento. Verificación: la suite de catálogo sigue verde tras cada extracción.

## 3. Usuarios base y asignaciones de rol

- [x] 3.1 RED: agregar a `tests/test_seed.py` los casos de cuatro usuarios (ADMIN, RECEPCION, MECANICO, CLIENTE), hash bcrypt verificable, una sola asignación abierta por usuario, `otorgada_por` del admin y al menos un `debe_cambiar_password=True`. Verificación: los tests fallan por datos ausentes.
- [x] 3.2 GREEN: implementar la carga de usuarios y roles usando `hash_password_sync()` antes de abrir la sesión y búsqueda idempotente por `email` y `(usuario_id, rol, revocada_en IS NULL)`. Verificación: los tests de 3.1 pasan sobre base vacía.
- [x] 3.3 TRIANGULATE: agregar el caso de re-ejecución con un `password_hash` existente distinto y verificar que no se sobrescribe ni se crea un rol duplicado. Verificación: el test pasa con el hash original intacto.
- [x] 3.4 REFACTOR: aislar la descripción de usuarios/roles en una estructura de datos declarativa. Verificación: suite de usuarios y roles verde.

## 4. Repuestos, stock inicial y movimientos `ALTA`

- [x] 4.1 RED: agregar casos que exijan los cuatro repuestos con su stock final, un único movimiento `ALTA` por repuesto, la igualdad `stock = SUM(movimiento_stock.cantidad)` y la no modificación del stock en re-ejecución. Verificación: los tests fallan por repuestos/movimientos ausentes.
- [x] 4.2 GREEN: implementar la carga de repuestos y sus movimientos `ALTA` con `usuario_id` del admin y `cuando` fijo. Verificación: los tests de 4.1 pasan.
- [x] 4.3 TRIANGULATE: agregar un caso con repuesto preexistente y stock distinto; verificar que no se agrega otro `ALTA` ni se reinicia el stock. Verificación: el test pasa y el invariante de stock se mantiene.
- [x] 4.4 REFACTOR: unificar el helper de "existe o crear" para repuestos y movimientos. Verificación: suite de repuestos verde.

## 5. Clientes, vehículos y órdenes demo

- [x] 5.1 RED: agregar casos de dos clientes (uno vinculado a `cliente@taller.local`), tres vehículos y tres órdenes demo con estados PENDIENTE, EN_REPARACION y TERMINADA. Verificación: los tests fallan por entidades ausentes.
- [x] 5.2 GREEN: implementar clientes y vehículos con búsqueda por `documento` y `patente` vigente. Verificación: los tests de clientes/vehículos pasan.
- [x] 5.3 GREEN: implementar órdenes, ítems con `precio_unitario` copiado del repuesto y `total` calculado con `Decimal` como suma de `cantidad × precio_unitario`. Verificación: los tests de totales y estados pasan.
- [x] 5.4 GREEN: implementar el historial completo por orden (desde `NULL`, sin saltos) y el movimiento `TERMINACION` de la orden TERMINADA, ajustando el `ALTA` para que el stock final siga siendo el declarado. Verificación: los tests de historial y del invariante `stock = SUM(movimientos)` pasan.
- [x] 5.5 TRIANGULATE: agregar un caso de doble ejecución que exija exactamente tres órdenes, sin ítems ni líneas de historial duplicadas. Verificación: los conteos no cambian entre la primera y la segunda ejecución.
- [x] 5.6 REFACTOR: extraer el armado de órdenes demo a una función declarativa y reutilizar el cálculo de totales. Verificación: suite de órdenes verde.

## 6. Auditoría, idempotencia global y ejecución segura

- [x] 6.1 RED: agregar el caso de un único evento `SISTEMA` / `seed_inicial` y un test de doble ejecución que compare todos los conteos (catálogo, usuarios, roles, repuestos, movimientos, clientes, vehículos, órdenes, ítems, historial, eventos). Verificación: el test falla mientras no exista el evento o mientras la segunda ejecución duplique filas.
- [x] 6.2 GREEN: implementar el registro del evento y cerrar la transacción única con logs de creado/existente y resumen final. Verificación: el test de 6.1 pasa y la segunda ejecución no altera ningún conteo.
- [x] 6.3 Implementar la guardia de producción y la confirmación de `--reset`: sin `--si` aborta con código 2 sin escribir; con `entorno=produccion` sin `--forzar` aborta antes de cualquier escritura. Verificación: `python seed.py --reset` devuelve código 2 y los conteos de la base no cambian; `ENTORNO=produccion python seed.py` devuelve código 2.
- [x] 6.4 Implementar `--reset --si` mediante la API de Alembic (`downgrade base` + `upgrade head`) antes de crear el loop del seed, y verificarlo manualmente en una base descartable de desarrollo. Verificación: tras el reset, la base queda migrada y el seed repuebla los mismos conteos que una carga limpia.
- [x] 6.5 REFACTOR: separar el parseo de argumentos, las guardias y la carga en funciones testeables. Verificación: suite de auditoría/idempotencia verde.

## 7. Espejo `test/seed.sql` y cierre de la estructura de `test/`

- [x] 7.1 RED: agregar un test que cargue `test/seed.sql` dos veces sobre una base limpia y exija los mismos conteos que `seed.py`, sin violar restricciones ni triggers. Verificación: el test falla porque el archivo no existe.
- [x] 7.2 GREEN: escribir `test/seed.sql` idempotente con `BEGIN`/`COMMIT`, `ON CONFLICT DO NOTHING`/`WHERE NOT EXISTS`, subconsultas por clave natural y hashes bcrypt congelados para las contraseñas de desarrollo. Verificación: el test de 7.1 pasa con doble carga.
- [x] 7.3 Agregar un test de paridad que compare claves naturales y conteos entre `seed.py` y `test/seed.sql`. Verificación: el test pasa y detecta cualquier fila faltante o sobrante en el espejo.
- [x] 7.4 Verificar la estructura final: `test/` contiene solo archivos `.http` y `seed.sql`; `scripts/verificar_solo_agregado.sql` existe; `tests/` contiene la suite pytest. Verificación: inspección de las tres carpetas y `pytest` verde desde la raíz.
- [x] 7.5 Ejecutar la verificación RN-15 sobre una base sembrada con `psql "$DATABASE_URL" -f scripts/verificar_solo_agregado.sql`. Verificación: los seis casos (UPDATE/DELETE en las tres tablas) reportan bloqueo o SKIP por tabla vacía, nunca un fallo de aserción.

## 8. Documentación y sincronización del roadmap

- [x] 8.1 Actualizar `README.md` con `python seed.py`, `python seed.py --reset --si`, `pytest tests/`, tabla de credenciales de desarrollo y advertencia de que no deben usarse fuera de local. Verificación: ejecutar los comandos documentados tal como están escritos.
- [x] 8.2 Actualizar `knowledge-base/02_descripcion_general.md` con la estructura definitiva: `seed.py`, `test/` (solo `.http` + `seed.sql`), `tests/` (pytest) y `scripts/` (verificación RN-15). Verificación: no quedan referencias a `test/solo_agregado.sql` ni a `conftest.py` dentro de `test/`.
- [x] 8.3 Agregar la regla de organización de pruebas a `AGENTS.md` y su copia `CLAUDE.md` (misma redacción en ambos). Verificación: ambos archivos contienen la regla y `diff` entre las secciones correspondientes no muestra divergencias.
- [x] 8.4 Actualizar `CHANGES.md`: nota de convención de carpetas, referencias de C-07 y C-20 a `scripts/verificar_solo_agregado.sql`, y rutas de test de C-01/C-05 a `tests/`. Verificación: `rg "test/solo_agregado|test/conftest"` no devuelve resultados en `CHANGES.md`.

## Workflow follow-up

- Marcar `[x]` el change C-08 en `CHANGES.md` y archivar con `/opsx:archive seed-inicial`.
- Revisar humanamente credenciales, roles sembrados y el comportamiento de `--reset` antes de dar el change por cerrado.
