# repuestos-stock Specification

## Purpose
Gestión del catálogo de repuestos del taller con stock gobernado exclusivamente por movimientos de stock, reposición, consulta de movimientos e historial de cambios de precio, respetando RN-14 y RN-20.

## Requirements

### Requirement: Listado paginado de repuestos
El sistema SHALL devolver un listado paginado de repuestos vigentes con búsqueda opcional por descripción mediante `ILIKE`. Los parámetros `page` y `size` MUST respetar el contrato de paginación. Un usuario sin autenticación MUST recibir 401.

#### Scenario: Listado exitoso
- **WHEN** un usuario autenticado solicita `GET /repuestos`
- **THEN** responde 200 con una página de repuestos vigentes

#### Scenario: Búsqueda por descripción
- **WHEN** se envía `q=filtro`
- **THEN** la respuesta contiene solo repuestos cuya descripción coincide con `ILIKE`

#### Scenario: Paginación inválida
- **WHEN** `page` o `size` son inválidos
- **THEN** responde 422

### Requirement: Consulta de repuesto por id
El sistema SHALL devolver un repuesto vigente por id. Un repuesto inexistente o dado de baja MUST responder 404.

#### Scenario: Repuesto existente
- **WHEN** se consulta un repuesto vigente
- **THEN** responde 200 con el repuesto

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se consulta un id inexistente o borrado
- **THEN** responde 404

### Requirement: Alta de repuesto con stock inicial
El sistema SHALL permitir crear un repuesto con código, descripción, precio y stock inicial, solo para usuarios ADMIN. El código MUST ser único entre repuestos vigentes. Al crear, MUST registrarse un movimiento de stock de tipo ALTA con la cantidad inicial en la misma transacción. Los campos no declarados MUST ser rechazados con 422.

#### Scenario: Alta exitosa
- **WHEN** un ADMIN envía un repuesto válido
- **THEN** responde 201 y se persiste un movimiento de stock ALTA con la cantidad inicial

#### Scenario: Código duplicado vigente
- **WHEN** se crea un repuesto con código ya vigente
- **THEN** responde 409

#### Scenario: Sin rol ADMIN
- **WHEN** un usuario sin rol ADMIN invoca POST /repuestos
- **THEN** responde 403

### Requirement: Modificación parcial de repuesto
El sistema SHALL permitir modificar descripción y/o precio de un repuesto vigente, solo para ADMIN. El campo `stock` MUST NOT ser editable por PATCH; si se envía MUST rechazarse con 422 o 400. Si el precio nuevo difiere del anterior, MUST insertarse una línea en `historial_precio_repuesto` en la misma transacción. Si el precio no cambia, MUST NOT generarse línea de historial. Si `precio_nuevo <= precio_anterior`, MUST responder 409.

#### Scenario: Cambio de descripción
- **WHEN** un ADMIN envía PATCH solo con descripción
- **THEN** responde 200 y no se genera línea de historial

#### Scenario: Cambio de precio mayor
- **WHEN** un ADMIN envía PATCH con precio mayor al anterior
- **THEN** responde 200 y se genera una línea en historial_precio_repuesto

#### Scenario: PATCH sin cambio de precio
- **WHEN** un ADMIN envía PATCH con el mismo precio
- **THEN** responde 200 y no se genera línea de historial

#### Scenario: Precio menor o igual rechazado
- **WHEN** un ADMIN envía PATCH con precio menor o igual al anterior
- **THEN** responde 409

#### Scenario: Intento de editar stock
- **WHEN** un PATCH incluye el campo `stock`
- **THEN** responde 422 o 400

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se hace PATCH sobre un id inexistente o borrado
- **THEN** responde 404

### Requirement: Baja lógica de repuesto
El sistema SHALL realizar borrado lógico de un repuesto vigente y responder 204, solo para ADMIN. Un repuesto inexistente o ya dado de baja MUST responder 404.

#### Scenario: Baja exitosa
- **WHEN** un ADMIN da de baja un repuesto vigente
- **THEN** responde 204 y el repuesto queda con `borrado_en` no nulo

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se da de baja un id inexistente o ya borrado
- **THEN** responde 404

### Requirement: Reposición de stock
El sistema SHALL permitir reponer stock de un repuesto vigente mediante `POST /repuestos/{id}/reponer`, solo para ADMIN, registrando un movimiento de stock en la misma transacción. La cantidad MUST ser mayor a cero. El stock resultante MUST ser no negativo.

#### Scenario: Reposición exitosa
- **WHEN** un ADMIN repone una cantidad positiva
- **THEN** responde 200 y se registra un movimiento de stock

#### Scenario: Cantidad inválida
- **WHEN** la cantidad es cero o negativa
- **THEN** responde 422

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se repone sobre un id inexistente o borrado
- **THEN** responde 404

### Requirement: Consulta de movimientos de stock
El sistema SHALL exponer el historial de movimientos de stock de un repuesto vigente, solo para ADMIN. Un repuesto inexistente o dado de baja MUST responder 404.

#### Scenario: Consulta exitosa
- **WHEN** un ADMIN consulta movimientos de un repuesto vigente
- **THEN** responde 200 con la lista de movimientos

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se consulta movimientos de un id inexistente o borrado
- **THEN** responde 404

### Requirement: Consulta de historial de precios
El sistema SHALL exponer el historial de cambios de precio de un repuesto vigente, solo para ADMIN. Un repuesto inexistente o dado de baja MUST responder 404.

#### Scenario: Consulta exitosa
- **WHEN** un ADMIN consulta precios de un repuesto vigente
- **THEN** responde 200 con la lista de cambios de precio

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se consulta precios de un id inexistente o borrado
- **THEN** responde 404
