# Lecciones aprendidas — TP Taller Mecánico (Grupo Aura, Comisión 4)

> **Qué es este documento.** Una retrospectiva de los errores que nos costaron puntos en la
> devolución (`docs/Correccion_Aura.pdf`, 75,5/100). **No describe el sistema actual ni propone
> parches**: es material de estudio para el próximo trabajo y para el agente que lo va a construir.
>
> **Cómo usarlo.**
> - Si sos el agente del próximo TP: leé §2, §3 y §5 antes de escribir la primera línea.
> - Si sos una persona del grupo: leé §1, §4 y §6.
> - Copiá este archivo al repo del próximo trabajo y referencialo desde `AGENTS.md`.
>
> **Regla de oro:** la consigna no es un documento de contexto, es el contrato de aceptación.
> Todo lo que no esté escrito ahí, no se inventa.

**Índice**

1. [Resultado y mapa del puntaje](#1-resultado-y-mapa-del-puntaje)
2. [Los ocho errores de fondo](#2-los-ocho-errores-de-fondo)
3. [Tabla completa de hallazgos](#3-tabla-completa-de-hallazgos)
4. [Por qué 434 tests en verde no alcanzaron](#4-por-qué-434-tests-en-verde-no-alcanzaron)
5. [Reglas duras para el próximo TP](#5-reglas-duras-para-el-próximo-tp)
6. [Checklist de entrega (clean room)](#6-checklist-de-entrega-clean-room)
7. [Hallazgos «sin descuento»](#7-hallazgos-sin-descuento-que-igual-hay-que-corregir)
8. [Las diez frases para llevar](#8-las-diez-frases-para-llevar)
9. [Anexos](#anexo-a--evidencia-reproducible-de-los-hallazgos-principales)

---

## 1. Resultado y mapa del puntaje

| Criterio | Máximo | Obtenido | Perdido | Causa raíz en una línea |
|---|---:|---:|---:|---|
| 1. Proyecto, configuración y ciclo de vida | 8 | 6 | **2** | Config con `DATABASE_URL` monolítica y motor creado al importar |
| 2. Modelos, relaciones y migraciones | 14 | 10 | **4** | Faltaron índices de FK, navegación uno-a-uno y comentario de revisión |
| 3. Contratos y CRUD | 10 | 8 | **2** | Códigos HTTP y envoltorio de paginación distintos a los casos |
| 4. Autenticación | 16 | 12 | **4** | `iat` string, bcrypt sin rounds, rate limit sin reset, cookie no reemitida |
| 5. Autorización | 14 | 11,5 | **2,5** | Permisos después del estado; cambio obligatorio incompleto |
| 6. Repositorios y Unit of Work | 20 | 11 | **9** | El UoW quedó invertido: servicio lo construye, router confirma |
| 7. Integridad: solo agregado e intento de acceso | 10 | 9 | **1** | Comentario que no explica el porqué ni el costo |
| 8. Lecturas sin N+1 y asincronía | 8 | 8 | **0** | — |
| **Total** | **100** | **75,5** | **24,5** | |

**Lectura rápida:** el 53 % del puntaje perdido (13 de 24,5) está en dos criterios:
**Unit of Work (9)** y **modelos/migraciones (4)**. No fueron bugs exóticos: fueron decisiones de
arquitectura y de prolijidad que la suite de tests no castigaba.

**Casos de prueba:** 7 de 19 completamente conformes (C-01, C-02, C-04, C-06, C-12, C-15, C-17).
Fallaron C-03, C-05, C-07, C-08, C-09, C-10, C-11, C-13, C-14, C-16, C-18 y C-19 (varios por una
o dos comprobaciones).

---

## 2. Los ocho errores de fondo

### E-01 — El Unit of Work quedó invertido (9 puntos)

**Qué pasó.** La consigna define tres responsabilidades distintas:

| Capa | Responsabilidad según la consigna |
|---|---|
| `router.py` | **Construye** el Unit of Work, llama al servicio y traduce errores |
| `service.py` | **Recibe** el Unit of Work y **lo abre** (`async with uow:`) |
| `unit_of_work.py` | **Confirma o revierte al salir del bloque**; no cierra la sesión |

Nuestro código hizo otra cosa:

- El router recibió el UoW por `Depends` y llamó `await uow.commit()` a mano
  (`clientes/router.py:28`; lo mismo en `ordenes/router.py:48` y `repuestos/router.py:64`).
- El servicio no abrió el bloque: usó el UoW como si fuera un simple contenedor de repositorios.
- En `usuarios` el problema es peor: en `service.py:150`, `:221` y `:283` el servicio
  **construyó su propio** `UnitOfWork(sesion_admin)` a partir de una sesión cruda.

**Evidencia de la devolución.**
- 6.5 (1,5/3): «El Unit of Work confirma al salir, pero los routers llaman a `uow.commit()` a mano
  porque los servicios no abren el bloque».
- 6.6 (0/3): «El servicio construye su Unit of Work» (tres ubicaciones).
- 6.7 (1,5/3): las operaciones de varias escrituras quedaron repartidas y sin un dueño claro.

**Por qué pasó.** Confundimos «tener un UoW» con «usar el UoW como frontera transaccional».
Los tests verificaban que el commit ocurría (y ocurría), pero no **quién** lo ejecutaba. La
arquitectura se validó por el resultado, no por la responsabilidad.

**Regla para el próximo TP.** El router construye; el servicio abre; solo `__aexit__` confirma.
Si aparece `commit()` fuera de `app/core/unit_of_work.py`, está mal. Si aparece
`UnitOfWork(` fuera de un router (o de la definición en `app/core/unit_of_work.py`), está mal.

---

### E-02 — La paginación no cumplió el contrato HTTP (2 puntos, pero rompió 3 casos)

**Qué pasó.** La consigna pide un envoltorio exacto:

```json
{ "items": [...], "total": 4, "page": 1, "size": 2, "pages": 2 }
```

con `page` desde 1, `size` de 1 a 100 (**por defecto 20**), página más allá de la última → **422**,
y cero resultados → **una página vacía**.

Nuestro `Page` se construyó como un modelo Pydantic con campos `pagina` y `tamanio`, más
`@property page/size` y un override de `model_dump()` que renombraba las claves. Los tests
llamaban `page.model_dump()` y veían `page`/`size`: pasaban. Pero FastAPI serializa
`response_model` **por campos declarados**, no por `model_dump()`. La respuesta real era:

```json
{ "items": [...], "total": 1, "pagina": 1, "tamanio": 10 }
```

Sin `page`, sin `size`, sin `pages`. Además el default era 10 (no 20) y `page=999` devolvía 200
con lista vacía (no 422).

**Evidencia de la devolución.**
- 3.5 (1/2): `/eventos` sin envoltorio; `page=999` → 200 en vez de 422.
- C-08 (14/16): «no se cumple `/eventos` con envoltorio».
- C-16 (22/32): sin envoltorio; `size` por defecto «sin dato»; `pages` «sin dato»; `page=2` con
  filtro → 200 en vez de 422; cero resultados sin `pages`.

**Por qué pasó.** Testeamos el objeto, no el cable. Es el error más peligroso de todos porque
**la suite queda verde y la API queda mal**.

**Regla para el próximo TP.** Todo contrato se testea con `TestClient`/`httpx` contra el JSON
HTTP, nunca contra `model_dump()`. Si el campo no aparece en `response.json()`, no existe.

---

### E-03 — Faltaron índices de FK y una navegación (4 puntos)

**Qué pasó.** Siete claves foráneas quedaron sin índice:

- `asignacion_rol.otorgada_por`
- `historial_estado_orden.desde_estado`
- `historial_estado_orden.hasta_estado`
- `historial_estado_orden.orden_id`
- `historial_estado_orden.usuario_id`
- `historial_precio_repuesto.repuesto_id`
- `historial_precio_repuesto.usuario_id`

Y `Usuario` no declaró la navegación uno-a-uno opcional hacia `Cliente` (2.4).

**Evidencia de la devolución.** 2.4 (1/2) y 2.5 (**0/2**).

**Por qué pasó.** PostgreSQL no indexa automáticamente las FK. Como los tests funcionales no
miden planes de ejecución, nadie lo notó. La navegación faltante tampoco rompía ningún endpoint:
simplemente no existía.

**Regla para el próximo TP.** Toda FK lleva índice, salvo que sea la PK o ya esté cubierta por
un índice compuesto que empiece por esa columna. Verificarlo con una consulta a
`pg_indexes`/`information_schema` y dejar la evidencia en el repo. Toda relación declarada en el
modelo debe tener su navegación inversa.

---

### E-04 — `seed.py` no reprodujo los datos de la consigna

**Qué pasó.** La consigna lista datos exactos que los casos de prueba usan:

- Usuarios `admin@example.com`, `admin2@example.com`, `recepcion@example.com`,
  `mecanico@example.com`, `mecanico2@example.com`, `cliente@example.com` y
  `nuevo@example.com` (con cambio de contraseña obligatorio).
- Clientes Laura (con usuario y dos vehículos) y Jorge (sin usuario, un vehículo).
- Repuestos: filtro de aceite (stock 10), pastillas (4), **bujía (2)** y aceite por litro (20),
  cada stock como movimiento «Stock inicial».
- Órdenes 1 (PENDIENTE, primer vehículo de Laura) y 2 (EN_REPARACION, vehículo de Jorge,
  asignada a `mecanico@example.com`, **con 4 bujías cuando hay 2**).
- Historial de precios: filtro de aceite de 8000 a 8500.
- Historial de seguridad: actor `SISTEMA`, «Carga de los datos iniciales».

Nuestro seed usó `@taller.local`, cuatro usuarios, ningún `admin2`/`mecanico2`/`nuevo`, ninguna
bujía y precios distintos. El corrector tuvo que **renombrar correos y agregar datos a mano en la
base** para poder correr los casos.

**Evidencia de la devolución.** Nota final: «`seed.py` no carga los datos de la consigna».
Afectó de forma transversal a C-01..C-19.

**Por qué pasó.** Tratamos el seed como «datos demo» y no como **fixture de aceptación**. Los
tests creaban sus propios datos con helpers, así que el seed nunca se ejercitó como contrato.

**Regla para el próximo TP.** El seed es parte de la puesta en marcha y es el fixture oficial.
Debe crear **exactamente** los emails, patentes, códigos, stocks y órdenes que lista la consigna.
Un test debe afirmar esos valores leyendo la base después de `python seed.py`.

---

### E-05 — La configuración no siguió la forma pedida (2 puntos + credenciales observadas)

**Qué pasó.** La consigna pide:

- `app/core/config.py` con `Settings` de `pydantic-settings`.
- La dirección armada con las variables sueltas `POSTGRES_USER`, `POSTGRES_PASSWORD`,
  `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` y un `@computed_field`.
- Ninguna contraseña ni clave en el código, en `alembic.ini` ni en el repositorio.
- El ejemplo se llama `env.example`.

Nuestro código puso la implementación real en `app/core/configuracion.py`, usó un único
`DATABASE_URL`, dejó credenciales en `alembic.ini:60` y en `.env.example`, y el ejemplo quedó con
punto inicial. Al final agregamos un `app/core/config.py` que solo re-exportaba: el corrector leyó
el archivo real y encontró la violación igual.

**Evidencia de la devolución.**
- 1.2 (1/2): «la dirección se escribe entera en `DATABASE_URL`, sin `@computed_field` ni las
  variables `POSTGRES_*`; `.env.example` trae esa dirección con contraseña».
- Condición «No hay credenciales reales»: **Observada** (se corrigió igual por decisión del docente).
- Nota: «el archivo de ejemplo se llama `.env.example` y la consigna pide `env.example`».

**Por qué pasó.** Priorizamos la convención que nos resultaba familiar (`DATABASE_URL`) sobre la
que pedía el enunciado. Y creímos que un shim de compatibilidad alcanzaba; no alcanza: **el path
es parte del contrato**.

**Regla para el próximo TP.** La implementación vive en el path exacto que nombra la consigna.
Prohibido resolverlo con re-exports. `alembic.ini` no lleva `sqlalchemy.url` con credenciales: se
arma desde `Settings` en `migrations/env.py`. El ejemplo se llama `env.example` y no tiene
secretos.

---

### E-06 — Respondimos lo que el código podía, no lo que el caso pedía (≈4 puntos)

**Qué pasó.** Varios códigos HTTP salieron del camino feliz de nuestra implementación, no del
caso de prueba:

| Caso | Esperado | Obtuvimos | Causa |
|---|---|---|---|
| C-03 login con 40 € (80 bytes) | 422 | 401 | No validamos el límite de 72 bytes en el contrato |
| C-10 repuesto inexistente | 409 | 404 | Tratamos el faltante como «no encontrado» |
| C-13 mecánico inicia | 200 | 409 | El estado/rol del caso no coincidió con nuestra máquina de estados |
| C-13 queda asignado | 3 | 1 | La asignación observada no coincidió con la esperada |
| C-13 recepción cancela en reparación | 409 | 200 | `transicion_valida` permitía cancelar desde cualquier estado no final |
| C-11 otro mecánico no termina | 403 | 409 | Permiso después del estado, y sin chequear asignación |
| C-11 recepción no termina | 403 | 409 | Igual: el rol se validó en el router, no la regla del recurso |
| C-19 orden sobre vehículo dado de baja | (404, 409) | 201 | Decidimos «conservar propiedad» e ignoramos RN-16 |
| C-18 PATCH baja de precio | 200 | 409 | Inventamos «Precio nuevo debe ser mayor» |

**Evidencia de la devolución.** 3.3 (1/2), 5.1 (1,5/3), 6.1 (1,5/3), 6.7 (1,5/3).

**Por qué pasó.** Cada vez que el caso y nuestra implementación no coincidían, ajustábamos el
test a la implementación. La consigna tiene dos reglas de orden explícitas que no respetamos:

- **RN-12:** «El permiso se evalúa antes que el estado» → 403 antes que 409.
- **RN-11:** cancelar solo desde `PENDIENTE`; terminar solo el mecánico asignado o un admin.

**Regla para el próximo TP.** Cada caso `C-NN` se convierte en un test de aceptación con el
código y el cuerpo exactos. Si el test falla, se cambia el código, no el test. Los códigos se
deciden en este orden: **404 → 403 → 409 → 422**. Nunca al revés.

---

### E-07 — Escrituras derivadas incompletas y stock en dos lugares (1,5 puntos)

**Qué pasó.**

- `POST /repuestos` no dejó el movimiento de stock inicial (C-16). En el código el movimiento se
  crea solo si el campo se llama `stock` y es distinto de 0; la consigna pide `stock_inicial`. Con
  `extra="forbid"`, el nombre incorrecto da 422 y no deja ni repuesto ni movimiento.
- La devolución reporta que la primera línea de historial no se escribe al crear la orden (C-10).
  En el código la fila se inserta, pero `OrdenRead` no expone `historial`, así que el caso no puede
  verificarla en la respuesta.
- El stock se escribe en **dos** lugares: `ordenes/service.py:242` (terminación) y
  `repuestos/service.py:115` (reposición). RN-14 pide **un único punto de escritura**.
- El PATCH de precio rechazó una baja con 409, regla que la consigna no pide (C-18).

**Evidencia de la devolución.** 6.7 (1,5/3) y C-10/C-16/C-18.

**Por qué pasó.** Implementamos «lo que hacía falta para que el endpoint respondiera», no «todas
las escrituras que la regla de negocio exige en la misma transacción».

**Regla para el próximo TP.** Por cada operación de escritura, listar en el `design.md` **todas**
las filas que deben quedar (entidad + historial + movimiento + auditoría) y testearlas juntas. El
stock tiene un solo dueño: un servicio/función de stock; los demás lo llaman.

---

### E-08 — El `iat` y el cambio de contraseña (2,5 puntos)

**Qué pasó.**

- Emitimos `iat` como string ISO (`2026-11-02T02:28:53.551915+00:00`). El estándar JWT lo define
  como **NumericDate** (numérico). La devolución lo marcó dos veces (4.5 y 5.5).
- El login devuelve `debe_cambiar_password` **anidado** dentro de `usuario`, pero el ejemplo de la
  consigna lo pone en el **nivel superior** de la respuesta.
- `/auth/yo` devuelve los roles vigentes de la base, pero no los roles del token: no puede
  «mostrar la diferencia» que pide C-07.
- El `200` de `/auth/cambiar-password` **no reemite cookie**. Nuestra docstring decía «por RN-07
  el token usado queda inválido y el cliente debe volver a autenticarse», pero C-09 espera
  exactamente lo contrario: «la cookie nueva vale y la anterior da 401, sin esperar entre el login
  y el cambio».

**Evidencia de la devolución.** 4.5 (1/2), 4.7 (0,5/1), 5.5 (1/2), C-09 (14/16).

**Por qué pasó.** Leímos RN-07 como «no reemitir» cuando la regla dice «la que devuelve el propio
cambio, no deja de valer». Es decir: **hay que emitir una nueva**. Y el formato del claim lo
resolvimos por comodidad de comparación, no por estándar.

**Regla para el próximo TP.** `iat` y `exp` numéricos (NumericDate). Para comparar con
microsegundos, usar un claim propio o un `float`; nunca un string ISO en un claim estándar. Toda
respuesta se compara contra el ejemplo literal de la consigna, campo por campo.

---

## 3. Tabla completa de hallazgos

> «Puntos» es lo perdido en ese indicador. «Regla» remite a §5.

### Criterio 1 — Proyecto, configuración y ciclo de vida (6/8)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 1.2 | Configuración | `POSTGRES_*` + `@computed_field`; ejemplo sin secretos | `DATABASE_URL` monolítica; credenciales en `alembic.ini` y `.env.example` | 1 | R-09 |
| 1.3 | Motor, fábrica y sesión | Motor y fábrica en `lifespan`/`app.state`; pool en config; `get_session` lee de `app.state` | Motor y fábrica al importar (`database.py:25-26`); `get_session` usa el global; sin `pool_size` | 1 | R-10 |

### Criterio 2 — Modelos, relaciones y migraciones (10/14)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 2.4 | Uno a uno opcional | `Usuario.cliente` navegable | Sin navegación | 1 | R-05 |
| 2.5 | Índices y navegación | Índice en cada FK | 7 FK sin índice | 2 | R-05 |
| 2.6 | Migración autogenerada | Comentario de revisión línea por línea | `002` sin comentario de qué se leyó | 1 | R-19 |

### Criterio 3 — Contratos y CRUD (8/10)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 3.3 | Códigos y mensajes | 422/409/200/403 según el caso | 401/404/409/200/409 | 1 | R-07 |
| 3.5 | Paginación | `{items,total,page,size,pages}`, size 20, page>última 422 | `pagina/tamanio`, sin `pages`, size 10, page=999 → 200 | 1 | R-06 |

### Criterio 4 — Autenticación (12/16)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 4.1 | bcrypt fuera del bucle | Costo declarado en config | `bcrypt.gensalt()` sin rounds | 1,5 | R-11 |
| 4.3 | Límite contado en la tabla | El éxito reinicia el conteo | [401,429,429,429] en vez de [401,401,401,401] | 1 | R-13 |
| 4.5 | Token | `iat` numérico | `iat` string ISO | 1 | R-12 |
| 4.7 | Registro y `/auth/yo` | `/auth/yo` muestra la diferencia | No la muestra | 0,5 | R-12 |

### Criterio 5 — Autorización (11,5/14)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 5.1 | 401 vs 403 | Permiso antes que estado | 409 antes que 403 | 1,5 | R-07 |
| 5.5 | Cambio obligatorio | `iat` con fracción; `debe_cambiar_password` true; cookie nueva | Falla en las tres; control repetido en rutas | 1 | R-14 |

### Criterio 6 — Repositorios y Unit of Work (11/20)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 6.1 | Dos jerarquías | Orden sobre vehículo dado de baja → 404/409 | 201 | 1,5 | R-07 |
| 6.4 | Repositorios y precarga | Precarga dentro del repositorio | `selectinload` en `clientes/service.py:24` | 1,5 | R-04 |
| 6.5 | UoW base | Servicio abre; `__aexit__` confirma | Router llama `commit()` | 1,5 | R-03 |
| 6.6 | Quién crea, abre y cierra | Router crea, servicio abre | Servicio construye `UnitOfWork(...)` en 3 lugares | 3 | R-03 |
| 6.7 | Varias escrituras | Historial inicial + movimiento de stock + un solo punto de stock | Faltan escrituras; stock en dos lugares; 409 inventado | 1,5 | R-15/R-16 |

### Criterio 7 — Integridad (9/10)

| # | Indicador | Esperado | Obtenido | Pts | Regla |
|---|---|---|---|---:|---|
| 7.3 | Excepción declarada | Comentario con el porqué y el costo | Dice «transacción independiente» sin explicar | 1 | R-22 |

### Criterio 8 — Lecturas sin N+1 y asincronía (8/8)

Sin hallazgos. Este criterio se resolvió bien: `selectinload` explícito, consultas fijas con 2 y
con 4 ítems (6 SELECT en ambos casos), sin bloqueos en el loop y aviso posterior a la respuesta.

### Casos que fallaron por el envase, no por la lógica

- **C-14 (26/27):** el comportamiento de solo-agregado estaba bien; faltó `test/solo_agregado.sql`
  en la ruta pedida. Un archivo mal ubicado costó el caso completo.
- **C-08 y C-16:** el envoltorio de paginación y el 422 de página inexistente.
- **C-09:** el formato de la respuesta de login y la reemisión de la cookie.

La conclusión se repite: **el artefacto y el formato son parte del caso**, no detalles de
presentación.

---

## 4. Por qué 434 tests en verde no alcanzaron

Esta es la lección más importante para el próximo proyecto.

1. **Los tests nacieron del código, no de la consigna.** Escribimos nuestros changes internos
   (también bautizados `C-01..C-20`, una colisión con los casos `C-NN` de la consigna que conviene
   evitar) a partir de nuestra knowledge base. Cuando la KB se desvió del enunciado, el test
   congeló la desviación. Un test que valida una interpretación equivocada es peor que no tener
   test: da falsa confianza.
2. **Testeamos modelos, no respuestas HTTP.** `tests/test_pagination.py` afirma
   `page.model_dump()["page"] == 1` y pasa, mientras la API devuelve `pagina`. Nunca abrimos el
   JSON real de un listado.
3. **No corrimos los casos `C-NN` literales.** La consigna trae 19 casos con resultados esperados.
   Deberían haber sido 19 tests de aceptación ejecutables, con el seed oficial como fixture. En su
   lugar escribimos tests por módulo, más cómodos y menos fieles.
4. **El seed nunca fue fixture.** Cada test creaba sus datos. Por eso el seed pudo estar mal
   durante 20 changes sin que nada fallara.
5. **No hubo «clean room».** El corrector corrió en Python 3.12 + PostgreSQL 16, base vacía,
   `.env` armado desde el ejemplo. Nosotros corrimos en Python 3.13 + PostgreSQL 17, con variables
   de entorno y una base migrada muchas veces. Varias diferencias (nombres de archivo, datos del
   seed, credenciales) solo aparecen en limpio.
6. **Los artefactos se nombraron según nuestra convención.** `scripts/verificar_solo_agregado.sql`
   en vez de `test/solo_agregado.sql`; `.env.example` en vez de `env.example`; `configuracion.py`
   en vez de `config.py`. El nombre y la ruta son parte de la entrega.
7. **Los shims taparon el problema.** `config.py`, `security.py` y `pagination.py` re-exportaban.
   El código «importaba», pero la implementación seguía en el archivo incorrecto. Un shim sirve
   para compatibilidad, nunca para cumplir una estructura obligatoria.
8. **Inventamos reglas para tapar huecos.** «El precio solo sube», «el vehículo dado de baja se
   puede usar», «cambiar contraseña no reemite cookie». Cada invención costó puntos y ninguna
   estaba pedida.

**La métrica correcta no es «tests en verde»: es «casos de la consigna en verde».**

---

## 5. Reglas duras para el próximo TP

> Copiar esta sección al `AGENTS.md` del próximo proyecto. Cada regla es verificable con un
> comando o una inspección. Si una regla no se puede verificar, no es una regla: es un deseo.

### Contrato y alcance

- **R-01. La consigna manda.** Toda regla de negocio se cita con su RN y su línea. Si el código y
  la consigna difieren, se cambia el código. Si hay contradicción entre una RN y un caso `C-NN`,
  se implementa el caso y se deja la contradicción documentada; no se inventa un 409.
- **R-02. El path y el nombre son contrato.** `app/core/config.py`, `app/core/security.py`,
  `app/core/paginacion.py`, `test/solo_agregado.sql`, `env.example`. La implementación vive ahí,
  no en un re-export.
- **R-07. Orden de códigos:** 404 (no existe) → 403 (no puede) → 409 (conflicto de estado/negocio)
  → 422 (contrato). Nunca al revés. RN-12: permiso antes que estado.
- **R-17. No inventar reglas.** Si la consigna no pide un 409, no se agrega. Si una RN y un caso
  se contradicen, se documenta y se prioriza el caso.

### Arquitectura

- **R-03. Unit of Work:** el router lo construye, el servicio lo abre con `async with`, solo
  `__aexit__` confirma. Prohibido `commit()` en router, servicio o repositorio. Prohibido
  `UnitOfWork(...)` dentro de un servicio.
- **R-04. Precarga en el repositorio.** `selectinload`/`joinedload` vive en `repository.py`.
  Servicios y routers no arman consultas de precarga.
- **R-10. Recursos en `lifespan`.** Motor y `sessionmaker` se crean en `lifespan` y se guardan en
  `app.state`; `get_session` los lee de `app.state`. Nada de motores al importar. `pool_size` en
  `Settings`.
- **R-15. Un solo punto de escritura de stock.** Alta con stock inicial, reposición y terminación
  pasan por la misma función; toda variación deja `movimiento_stock`.
- **R-16. Escrituras derivadas en la misma transacción.** Crear orden → historial inicial.
  Cambiar precio → historial de precio. Terminar → movimientos + historial + stock. Todo o nada.

### Datos y esquema

- **R-05. Índices y navegación.** Toda FK lleva índice; toda relación tiene navegación inversa.
  Verificar con `pg_indexes` y con un test que recorra `ForeignKeyConstraint`.
- **R-06. Paginación:** `{items,total,page,size,pages}`, `page` desde 1, `size` 1..100 con default
  **20**, página fuera de rango **422**, cero resultados **una página vacía**. `total` con los
  mismos filtros. Testear el JSON HTTP.
- **R-08. Seed = fixture de aceptación.** Emails, patentes, códigos, stocks, órdenes e historiales
  exactos de la consigna. Un test los afirma después de `python seed.py`.
- **R-09. Configuración:** `POSTGRES_*` + `@computed_field`; `alembic.ini` sin credenciales;
  `env.example` sin secretos; `JWT_SECRET` obligatorio, sin default.
- **R-19. Migración autogenerada revisada.** Comentario en el archivo: qué se comparó, qué se
  cambió a mano y por qué. `alembic check` limpio antes de entregar.

### Seguridad y autenticación

- **R-11. bcrypt:** `rounds` en `Settings`; `asyncio.to_thread` + semáforo; máximo 72 bytes en el
  contrato → **422**, no 401/500.
- **R-12. JWT:** `sub`, `iat`, `exp` numéricos; roles informativos; comparar `iat` con
  `password_cambiada_en` sin truncar. `/auth/yo` debe reflejar la diferencia.
- **R-13. Rate limit:** 5 fallos/60 s por `(email, ip)`; el éxito **reinicia el conteo** sin borrar
  las filas; `Retry-After` correcto.
- **R-14. Cambio de contraseña:** la respuesta **entrega cookie nueva**; la anterior da 401. El
  gating de RN-06 es un grupo de rutas, no un chequeo repetido por handler.

### Calidad y entrega

- **R-18. Tests de aceptación literales.** Un test por `C-NN`, contra HTTP, con el seed oficial.
  Prohibido testear `model_dump()` para contratos de API.
- **R-20. Ninguna entrada inválida termina en 500.** Probar: id de ruta enorme, cantidad enorme,
  NUL en texto, NUL en `q`, string de 10 MB, página fuera de rango, JSON malformado.
- **R-21. Artefactos de test:** `test/*.http` por módulo + `test/solo_agregado.sql`. Nada de
  `scripts/` para lo que la consigna pide en `test/`.
- **R-22. Comentarios con porqué y costo.** Un comentario que dice «transacción independiente»
  debe decir **por qué** y **cuánto cuesta** (conexión extra, ventana de inconsistencia, etc.).

---

## 6. Checklist de entrega (clean room)

> Ejecutar en una carpeta nueva, con la versión de Python y PostgreSQL de la cátedra.
> Si un paso falla, no se entrega.

### 6.1 Preparación

- [ ] Clonar/copiar el repo en una carpeta limpia (sin `.env`, sin `__pycache__`, sin `.pytest_cache`).
- [ ] Crear entorno virtual con **Python 3.12** (el de la cátedra, no el local).
- [ ] `pip install -r requirements.txt`.
- [ ] Copiar `env.example` → `.env` y completar **solo** `POSTGRES_*` y `JWT_SECRET`.
- [ ] Confirmar que `alembic.ini` **no** tiene usuario ni contraseña.
- [ ] Confirmar que `env.example` **no** tiene secretos.

### 6.2 Esquema y datos

- [ ] Crear base vacía.
- [ ] `alembic upgrade head` → sin error.
- [ ] `alembic downgrade base` → sin error.
- [ ] `alembic upgrade head` → sin error.
- [ ] `alembic check` → «No new upgrade operations detected».
- [ ] `python seed.py` → sin error.
- [ ] Verificar en psql: 4 estados, 7 usuarios, 2 clientes, 3 vehículos, 4 repuestos (incluida la
  bujía), 2 órdenes, historial de precio 8000→8500, evento `SISTEMA`.

### 6.3 Casos de aceptación

- [ ] Correr los 19 casos `C-01..C-19` de la consigna, uno por uno, con el seed oficial.
- [ ] Para cada caso, comparar **status** y **body** contra el texto de la consigna.
- [ ] Correr los `.http` de `test/` con la extensión REST Client.
- [ ] Verificar que `test/solo_agregado.sql` existe y que los 6 rechazos + la FK dan error.
- [ ] Verificar paginación: `size` default 20, `pages`, `page=999` → 422, cero resultados → 1 página.

### 6.4 Calidad

> Los `grep` son ilustrativos. En Windows usar `Select-String` o `rg` (ripgrep).

- [ ] `pytest` completo en verde **contra PostgreSQL real** (nunca SQLite).
- [ ] `python -m compileall app main.py seed.py` sin error.
- [ ] `rg "commit\(\)" app/` → solo en `app/core/unit_of_work.py`.
- [ ] `rg "UnitOfWork\(" app/modules/*/service.py` → vacío.
- [ ] `rg "selectinload" app/modules/*/service.py` → vacío (solo repositorios).
- [ ] `rg "bcrypt\.gensalt\(\)" app/` → con `rounds=` desde config.
- [ ] Probar entradas extremas: id enorme, cantidad enorme, NUL, `q` con NUL → nunca 500.

### 6.5 Paquete

- [ ] Sin `.env`, sin `__pycache__`, sin `.pytest_cache`, sin `.ruff_cache`, sin tooling local.
- [ ] `requirements.txt`, `env.example`, `alembic.ini`, `migrations/`, `test/`, `tests/`,
  `seed.py`, `main.py`, `README.md` presentes.
- [ ] README con integrantes, comisión, pasos de instalación y ejecución.
- [ ] Zip generado desde el commit final, no desde el working tree.

---

## 7. Hallazgos «sin descuento» que igual hay que corregir

La devolución aclara que estos desvíos **no descontaron**, pero los marca como diferencias con
los ejemplos. En el próximo TP conviene alinearlos desde el día uno:

1. **Subtotal por ítem.** La respuesta de una orden incluye `codigo`, `descripcion` y `subtotal`
   por ítem; nosotros devolvemos `repuesto_id`, `cantidad` y `precio_unitario`.
2. **Patente y cliente en la respuesta.** El ejemplo de orden trae `patente` y `cliente` en el
   nivel superior; nosotros solo anidamos `vehiculo`.
3. **Admin no inicia.** El ejemplo dice que `POST /ordenes/{id}/iniciar` lo hace un mecánico;
   nosotros permitimos ADMIN y RECEPCION.
4. **Detalle con historial.** `GET /ordenes/{id}` debe traer `historial`; nuestro `OrdenRead` no
   lo expone.
5. **Movimientos del repuesto.** El ejemplo muestra los movimientos del repuesto; verificar que el
   endpoint y el formato coincidan.
6. **Entradas extremas → 500.** La devolución sugiere probar id de ruta enorme, cantidad enorme,
   NUL en texto y `q` con NUL. Hoy pueden terminar en 500; RN-18 lo prohíbe.
7. **`env.example`.** Renombrar y actualizar el README.

---

## 8. Las diez frases para llevar

1. La consigna es el contrato; la KB es una hipótesis.
2. Un test verde sobre una interpretación equivocada es una trampa.
3. Testeá el JSON que viaja, no el objeto que queda en memoria.
4. El path y el nombre del archivo son parte de la entrega.
5. El router construye, el servicio abre, el UoW confirma.
6. Toda FK lleva índice; toda relación, navegación.
7. El seed es el fixture de aceptación, no un demo.
8. Permiso antes que estado; 404 antes que 403.
9. No inventes reglas: si no está en la consigna, no existe.
10. Antes de entregar, corré todo en una carpeta limpia con la versión de la cátedra.

---

## Anexo A — Evidencia reproducible de los hallazgos principales

> Comandos en bash. En PowerShell: reemplazar `grep` por `rg` (o `Select-String`) y el heredoc
> `python - <<'PY'` por un archivo `.py` o `python -c "..."`.

```bash
# 1. El UoW invertido
grep -rn "uow.commit()" app/modules/*/router.py
grep -rn "UnitOfWork(" app/modules/*/service.py

# 2. La paginación real (no la del modelo)
python - <<'PY'
from fastapi.encoders import jsonable_encoder
from app.core.paginacion import Page
p = Page(items=[{"id": 1}], total=1, page=1, size=10)
print(jsonable_encoder(p))          # {'items': ..., 'page': 1, 'size': 10}
print(Page[dict].model_json_schema()["properties"].keys())
# ['items', 'total', 'pagina', 'tamanio']  ← lo que FastAPI declara en response_model
PY

# 3. Credenciales en el repo
grep -n "sqlalchemy.url" alembic.ini
grep -n "DATABASE_URL" env.example .env.example

# 4. FK sin índice (en psql)
SELECT c.conrelid::regclass AS tabla, a.attname AS columna
FROM pg_constraint c
JOIN unnest(c.conkey) AS k(attnum) ON true
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid AND i.indkey[0] = k.attnum
  );

# 5. Stock escrito en dos lugares
grep -rn "stock *[-+]=" app/modules/*/service.py

# 6. Regla inventada
grep -rn "PRECIO_NO_MAYOR" app/
```

## Anexo B — Contradicciones detectadas en la consigna

Documentarlas sirve para no volver a elegir en silencio:

1. **RN-20 vs C-18.** RN-20 pide `CHECK precio_nuevo > precio_anterior`; C-18 espera que un PATCH
   que baja el precio de 15000 a 9000 devuelva 200 y deje historial (15000 → 9000). Ambas no pueden
   ser ciertas con el mismo CHECK. La corrección aplicó C-18. **Decisión para el próximo TP:**
   implementar el caso (permitir la baja) y dejar el CHECK como `precio_nuevo <> precio_anterior`,
   documentando la contradicción.
2. **`env.example` vs `.env.example`.** La consigna pide `env.example`; la devolución lo confirma.
   Usar ese nombre exacto.
3. **`iat` con fracción vs estándar JWT.** RN-07 pide comparar sin truncar; el estándar pide
   numérico. Solución: `iat` numérico con decimales (NumericDate admite fracción) o un claim
   propio para los microsegundos.

---

*Documento generado a partir de `docs/Correccion_Aura.pdf` y verificado contra el código del
commit `0b76075`. No se modificó ninguna línea del sistema.*
