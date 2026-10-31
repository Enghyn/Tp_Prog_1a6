# Spec Delta

## Purpose

Exposes the security event trail so an administrator can audit who did what and when, with stable ordering and pagination over the immutable `evento_seguridad` registry.

## ADDED Requirements

### Requirement: Consulta de auditoría restringida a ADMIN

`GET /eventos` SHALL exigir una sesión válida y un rol `ADMIN` vigente leído de la base en la misma petición.

#### Scenario: Petición sin sesión

- **WHEN** se invoca `GET /eventos` sin cookie `access_token`
- **THEN** la respuesta es `401` con `codigo = "CREDENCIALES_INVALIDAS"`

#### Scenario: Sesión válida sin rol ADMIN

- **WHEN** un usuario autenticado sólo con `MECANICO` vigente invoca `GET /eventos`
- **THEN** la respuesta es `403` con `codigo = "PERMISOS_INSUFICIENTES"`

#### Scenario: Rol ADMIN revocado en caliente

- **WHEN** un usuario cuyo rol `ADMIN` fue revocado después de emitir el token invoca `GET /eventos`
- **THEN** la respuesta es `403`, aunque el token siga sin expirar y declare `ADMIN`

### Requirement: Listado paginado de eventos

`GET /eventos` SHALL devolver una página de `evento_seguridad` con los campos `id`, `cuando`, `actor` y `accion` de cada evento, ordenada por `cuando` descendente y desempatada por `id` descendente, junto con `total`, `page` y `size`.

#### Scenario: Listado sin filtros

- **WHEN** un administrador invoca `GET /eventos` sin parámetros
- **THEN** la respuesta es `200` con `page = 1`, `size = 10`, `total` igual a la cantidad de eventos registrados y, como máximo, los 10 eventos más recientes

#### Scenario: Orden estable entre eventos del mismo instante

- **WHEN** existen dos eventos con el mismo `cuando`
- **THEN** el de `id` mayor aparece primero y el orden se repite igual en consultas sucesivas

#### Scenario: Página intermedia

- **WHEN** existen 12 eventos y se invoca `GET /eventos?page=2&size=10`
- **THEN** la respuesta es `200` con `total = 12`, `page = 2` y dos `items`, los dos eventos más antiguos

#### Scenario: Página fuera de rango

- **WHEN** se invoca una página posterior a la última disponible
- **THEN** la respuesta es `200` con `items = []` y el `total` real, no un `404`

#### Scenario: El listado no modifica la auditoría

- **WHEN** se consulta `GET /eventos` cualquier cantidad de veces
- **THEN** la cantidad de filas de `evento_seguridad` no cambia

### Requirement: Filtro por rango temporal

`GET /eventos` SHALL aceptar `desde` y `hasta` como instantes ISO-8601 con zona horaria, ambos inclusive, y devolver sólo los eventos cuyo `cuando` cae dentro del rango.

#### Scenario: Rango que incluye eventos

- **WHEN** se invoca `GET /eventos?desde=<T1>&hasta=<T2>` y existen eventos en `T1`, en el medio y en `T2`
- **THEN** la respuesta incluye los tres eventos y el `total` cuenta sólo esos

#### Scenario: Sólo cota inferior

- **WHEN** se envía únicamente `desde`
- **THEN** la respuesta incluye todos los eventos con `cuando >= desde`, sin cota superior

#### Scenario: Sólo cota superior

- **WHEN** se envía únicamente `hasta`
- **THEN** la respuesta incluye todos los eventos con `cuando <= hasta`, sin cota inferior

#### Scenario: Rango vacío

- **WHEN** `desde` es posterior a `hasta`
- **THEN** la respuesta es `422` con `codigo = "RANGO_FECHAS_INVALIDO"` y `items` no se devuelve

#### Scenario: Rango sin coincidencias

- **WHEN** el rango no contiene ningún evento
- **THEN** la respuesta es `200` con `items = []` y `total = 0`

### Requirement: Filtro por actor con coincidencia exacta

`GET /eventos` SHALL aceptar `actor` como filtro de igualdad estricta contra `evento_seguridad.actor`, combinable con el rango temporal y con la paginación.

#### Scenario: Actor existente

- **WHEN** se invoca `GET /eventos?actor=admin@taller.local` y existen eventos de ese actor y de otros
- **THEN** la respuesta incluye sólo los eventos cuyo `actor` es exactamente `admin@taller.local`

#### Scenario: Coincidencia parcial no filtra

- **WHEN** se invoca `GET /eventos?actor=admin` y no existe un actor exactamente igual a `admin`
- **THEN** la respuesta es `200` con `items = []` y `total = 0`

#### Scenario: Actor textual del sistema

- **WHEN** se invoca `GET /eventos?actor=SISTEMA`
- **THEN** la respuesta incluye los eventos cuyo `actor` es exactamente `SISTEMA`

#### Scenario: Filtros combinados

- **WHEN** se combinan `actor`, `desde` y `hasta`
- **THEN** el `total` y los `items` cuentan sólo los eventos que cumplen las tres condiciones

### Requirement: Contrato de paginación inválido

`GET /eventos` SHALL responder `422` cuando `page` sea menor que 1, `size` menor que 1 o mayor que 100, o cuando `desde`/`hasta` no sean instantes ISO-8601 válidos con zona horaria.

#### Scenario: Tamaño de página fuera de rango

- **WHEN** se invoca `GET /eventos?size=101`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"` y `detail[].loc` señala `size`

#### Scenario: Página cero

- **WHEN** se invoca `GET /eventos?page=0`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"`

#### Scenario: Fecha sin zona horaria

- **WHEN** se invoca `GET /eventos?desde=2026-10-31T10:00:00` sin offset
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"`

#### Scenario: Fecha con formato inválido

- **WHEN** se invoca `GET /eventos?hasta=ayer`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"`
