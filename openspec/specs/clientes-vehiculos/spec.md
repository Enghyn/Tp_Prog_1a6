# clientes-vehiculos Specification

## Purpose
Gestión de clientes y vehículos del taller: alta y consulta de clientes con sus vehículos, registro de vehículos por cliente, baja lógica de vehículos con guardas de órdenes abiertas y consulta de vehículos propios del cliente autenticado.

## Requirements

### Requirement: Alta de cliente
El sistema SHALL permitir crear un cliente con `nombre`, `documento` y `telefono` opcional, por usuarios con rol RECEPCION o ADMIN. El `documento` MUST ser único; si ya existe MUST responder 409 con código `CONFLICTO`. Los campos no declarados MUST ser rechazados con 422.

#### Scenario: Alta exitosa
- **WHEN** un usuario RECEPCION envía un cliente válido con documento nuevo
- **THEN** responde 201 con el cliente creado y sin datos sensibles

#### Scenario: Documento duplicado
- **WHEN** se intenta crear un cliente con un documento ya existente
- **THEN** responde 409 con código `CONFLICTO`

#### Scenario: Sin rol suficiente
- **WHEN** un usuario sin rol RECEPCION/ADMIN invoca POST /clientes
- **THEN** responde 403

### Requirement: Consulta de cliente con vehículos
El sistema SHALL devolver un cliente por id con sus vehículos precargados (selectinload, sin N+1). Si el cliente no existe o está dado de baja MUST responder 404.

#### Scenario: Cliente existente
- **WHEN** se consulta un cliente existente
- **THEN** la respuesta incluye la lista de vehículos del cliente

#### Scenario: Cliente inexistente
- **WHEN** se consulta un id inexistente
- **THEN** responde 404

### Requirement: Alta de vehículo por cliente
El sistema SHALL permitir registrar un vehículo (`patente`, `marca`, `modelo`, `anio` con 1950..2100) asociado a un cliente existente. La patente MUST ser única entre vehículos vigentes (`borrado_en IS NULL`); si ya existe una vigente MUST responder 409. Una patente de un vehículo dado de baja MUST poder reutilizarse.

#### Scenario: Alta exitosa
- **WHEN** se registra un vehículo con patente nueva para un cliente existente
- **THEN** responde 201 con el vehículo creado

#### Scenario: Patente duplicada vigente
- **WHEN** se registra un vehículo con patente ya vigente
- **THEN** responde 409 con código `CONFLICTO`

#### Scenario: Patente reusable tras baja lógica
- **WHEN** se registra un vehículo cuya patente existió pero fue dada de baja
- **THEN** la alta es exitosa

#### Scenario: Cliente inexistente
- **WHEN** se registra un vehículo para un cliente inexistente
- **THEN** responde 404

### Requirement: Baja lógica de vehículo
El sistema SHALL realizar borrado lógico de un vehículo (setear `borrado_en`) y responder 204. MUST rechazar con 409 si el vehículo tiene órdenes abiertas (`estado_orden.es_final = false`). Un vehículo inexistente o ya dado de baja MUST responder 404.

#### Scenario: Baja exitosa
- **WHEN** se da de baja un vehículo sin órdenes abiertas
- **THEN** responde 204

#### Scenario: Baja bloqueada por orden abierta
- **WHEN** se da de baja un vehículo con al menos una orden abierta
- **THEN** responde 409 con código `CONFLICTO`

#### Scenario: Vehículo inexistente o dado de baja
- **WHEN** se da de baja un id inexistente o ya borrado
- **THEN** responde 404

### Requirement: Consulta de vehículos propios
El sistema SHALL exponer `GET /mis-vehiculos` que devuelve únicamente los vehículos del cliente asociado al usuario autenticado (RN-17). Un usuario sin rol CLIENTE MUST recibir 403.

#### Scenario: Cliente ve solo sus vehículos
- **WHEN** un cliente autenticado consulta /mis-vehiculos
- **THEN** la respuesta contiene solo los vehículos de su cliente

#### Scenario: Sin rol CLIENTE
- **WHEN** un usuario sin rol CLIENTE invoca /mis-vehiculos
- **THEN** responde 403
