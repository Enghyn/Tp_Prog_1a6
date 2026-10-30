# seed-inicial Specification

## Purpose

Cargar de forma reproducible e idempotente el estado inicial conocido de la base del taller (catálogo, usuarios y roles, repuestos con stock, clientes, vehículos, órdenes demo y auditoría) y fijar la organización de los artefactos de prueba del repositorio.

## Requirements

### Requirement: Catálogo de estados canónico

El sistema SHALL cargar el catálogo `estado_orden` con exactamente cuatro filas canónicas: `PENDIENTE` (posición 1, no final), `EN_REPARACION` (posición 2, no final), `TERMINADA` (posición 3, final) y `CANCELADA` (posición 4, final), y SHALL converger a esos valores en cada ejecución (RN-19).

#### Scenario: Catálogo completo tras la carga

- **WHEN** se ejecuta el seed sobre una base migrada y vacía
- **THEN** `estado_orden` contiene exactamente las cuatro filas canónicas con su `posicion` y `es_final` correctos

#### Scenario: Re-ejecución sin duplicados ni derivas

- **WHEN** se ejecuta el seed por segunda vez
- **THEN** el catálogo sigue teniendo cuatro filas y sus valores canónicos no cambian

### Requirement: Usuarios y roles base

El sistema SHALL crear cuatro usuarios de desarrollo (ADMIN, RECEPCION, MECANICO y CLIENTE) con contraseña almacenada como hash bcrypt, cada uno con una única asignación de rol abierta, y al menos uno con `debe_cambiar_password=True`. Las contraseñas existentes no se sobrescriben en re-ejecuciones.

#### Scenario: Alta inicial de usuarios y roles

- **WHEN** se ejecuta el seed sobre una base sin usuarios
- **THEN** existen los cuatro usuarios, cada uno con exactamente una asignación abierta del rol esperado y al menos uno marcado para cambiar contraseña

#### Scenario: Re-ejecución respeta datos existentes

- **WHEN** un usuario base ya existe y se vuelve a ejecutar el seed
- **THEN** no se crea un usuario duplicado ni una segunda asignación abierta del mismo rol, y su `password_hash` no se modifica

### Requirement: Stock inicial gobernado por movimientos

El sistema SHALL crear repuestos con stock inicial positivo y, por cada uno, un `movimiento_stock` de motivo `ALTA` con cantidad igual al stock inicial (RN-14). El `stock` de cada repuesto SHALL ser igual a la suma de sus movimientos.

#### Scenario: Alta de repuestos genera movimiento ALTA

- **WHEN** se cargan repuestos que no existían
- **THEN** cada repuesto queda con su stock inicial y un único movimiento `ALTA` cuya cantidad coincide con ese stock

#### Scenario: Repuesto existente no se reinicia

- **WHEN** se re-ejecuta el seed y el repuesto ya existe
- **THEN** no se agrega otro movimiento `ALTA` ni se modifica su stock

#### Scenario: Stock consistente con el historial

- **WHEN** se suman todos los movimientos de un repuesto sembrado, incluidos los de terminación de órdenes demo
- **THEN** la suma coincide con el valor actual de `repuesto.stock`

### Requirement: Órdenes demo coherentes

El sistema SHALL crear tres órdenes demo en estados distintos del catálogo, con vehículo, falla identificable, ítems con precio unitario copiado del repuesto y `total` calculado en el servidor como la suma de `cantidad × precio_unitario`. Cada orden SHALL tener historial de estados desde `desde_estado = NULL` hasta su estado actual, sin saltos.

#### Scenario: Estados e importes válidos

- **WHEN** se ejecuta el seed
- **THEN** las tres órdenes existen con estados del catálogo, al menos un ítem cada una y un total igual a la suma de sus ítems

#### Scenario: Historial inicial presente

- **WHEN** se consulta el historial de una orden demo
- **THEN** la primera línea parte de `desde_estado = NULL` y la secuencia de estados termina en el estado actual de la orden

#### Scenario: Re-ejecución sin órdenes duplicadas

- **WHEN** se ejecuta el seed por segunda vez
- **THEN** siguen existiendo tres órdenes demo, sin líneas de ítems ni de historial duplicadas

### Requirement: Auditoría de la carga inicial

El sistema SHALL registrar en `evento_seguridad` un evento con `actor='SISTEMA'` y `accion='seed_inicial'` por carga efectiva, sin duplicarlo en re-ejecuciones.

#### Scenario: Evento único de sistema

- **WHEN** se ejecuta el seed dos veces
- **THEN** existe exactamente un evento con actor `SISTEMA` y acción `seed_inicial`

### Requirement: Ejecución idempotente y reset seguro

El sistema SHALL poder ejecutarse dos veces seguidas sin duplicar filas ni alterar datos ya cargados. La opción `--reset` SHALL ser destructiva, exigir confirmación explícita y SHALL negarse a operar cuando `entorno=produccion` salvo autorización explícita.

#### Scenario: Doble ejecución estable

- **WHEN** se ejecuta el seed dos veces consecutivas
- **THEN** los conteos de catálogo, usuarios, roles, repuestos, movimientos, clientes, vehículos, órdenes e historial no cambian entre la primera y la segunda ejecución

#### Scenario: Reset destructivo confirmado

- **WHEN** se invoca `--reset` sin confirmación explícita
- **THEN** el seed aborta sin borrar datos y explica cómo confirmar la operación

#### Scenario: Protección de producción

- **WHEN** el entorno configurado es `produccion` y no se pasó la autorización explícita
- **THEN** el seed aborta antes de escribir cualquier fila

### Requirement: Espejo SQL idempotente

El sistema SHALL proveer `test/seed.sql` como espejo idempotente del seed, apto para carga manual con `psql`, y SHALL ser el único archivo `.sql` dentro de `test/`.

#### Scenario: Carga manual repetible

- **WHEN** se ejecuta `test/seed.sql` dos veces sobre la misma base
- **THEN** los datos iniciales quedan cargados una sola vez, sin violar restricciones ni los triggers de solo-agregado

#### Scenario: Único SQL en test

- **WHEN** se inspecciona la carpeta `test/`
- **THEN** contiene archivos `.http` y exactamente un archivo `.sql`, llamado `seed.sql`

### Requirement: Organización de las pruebas del repositorio

El repositorio SHALL mantener la suite pytest en `tests/`, con `pytest.ini` apuntando `testpaths` a esa carpeta, y `test/` SHALL contener únicamente archivos `.http` y `seed.sql`.

#### Scenario: Sin archivos Python en test

- **WHEN** se inspecciona `test/`
- **THEN** no hay archivos `.py`, `conftest.py` ni `__init__.py`

#### Scenario: Pytest descubre la suite movida

- **WHEN** se ejecuta `pytest` desde la raíz del proyecto
- **THEN** descubre y ejecuta los tests de `tests/` sin necesidad de argumentos adicionales

#### Scenario: Verificación RN-15 reubicada

- **WHEN** se busca el script de verificación de tablas de solo-agregado
- **THEN** se encuentra en `scripts/verificar_solo_agregado.sql` y no dentro de `test/`
