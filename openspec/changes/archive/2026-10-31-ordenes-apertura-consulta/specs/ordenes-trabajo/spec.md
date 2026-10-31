# ordenes-trabajo Specification

## Purpose
Gestión de la apertura y consulta de órdenes de trabajo del taller: creación atómica con precios y totales calculados en servidor, historial inicial de estado, listado y detalle con precarga explícita, filtrado por estado, órdenes propias del cliente y catálogo de estados ordenado por posición.

## ADDED Requirements

### Requirement: Apertura de orden de trabajo
El sistema SHALL permitir a usuarios con rol RECEPCION o ADMIN crear una orden de trabajo con `vehiculo_id`, `falla` y una lista de ítems (`repuesto_id`, `cantidad`), creando la orden en estado PENDIENTE y una línea inicial de historial en la misma transacción. Los campos no declarados MUST ser rechazados con 422. Un usuario sin rol suficiente MUST recibir 403.

#### Scenario: Apertura exitosa
- **WHEN** un usuario RECEPCION o ADMIN envía una orden válida con ítems
- **THEN** responde 201 con la orden en estado PENDIENTE y el total calculado por el servidor

#### Scenario: Sin rol suficiente
- **WHEN** un usuario sin rol RECEPCION/ADMIN invoca POST /ordenes
- **THEN** responde 403

### Requirement: Entrada estricta de ítems
El sistema SHALL rechazar con 422 cualquier cuerpo que incluya `precio_unitario` o `total`, que contenga ítems con `repuesto_id` repetido, o cuya `cantidad` sea menor o igual a cero. Los ítems no pueden estar vacíos.

#### Scenario: Precio o total en el cuerpo
- **WHEN** el cuerpo incluye `precio_unitario` o `total`
- **THEN** responde 422

#### Scenario: Ítem repetido
- **WHEN** dos ítems comparten el mismo `repuesto_id`
- **THEN** responde 422

#### Scenario: Cantidad inválida
- **WHEN** algún ítem tiene `cantidad <= 0`
- **THEN** responde 422

#### Scenario: Sin ítems
- **WHEN** la lista de ítems está vacía
- **THEN** responde 422

### Requirement: Precios y total calculados en servidor
El sistema SHALL copiar el `precio_unitario` actual de cada repuesto vigente y calcular `total` como la suma de `cantidad * precio_unitario`, ignorando cualquier valor enviado por el cliente.

#### Scenario: Total calculado en servidor
- **WHEN** se envía un precio o total en el cuerpo (rechazado por entrada estricta) o solo cantidades
- **THEN** el total persistido es la suma calculada por el servidor a partir del catálogo

#### Scenario: Precio unitario copiado del catálogo
- **WHEN** se abre una orden válida
- **THEN** cada ítem persiste el precio vigente del repuesto en el momento de la apertura

### Requirement: Validación de repuestos vigentes
El sistema SHALL validar que cada repuesto referenciado exista y esté vigente. Un repuesto dado de baja MUST responder 409. Un repuesto inexistente MUST responder 404.

#### Scenario: Repuesto dado de baja
- **WHEN** un ítem referencia un repuesto con `borrado_en` no nulo
- **THEN** responde 409

#### Scenario: Repuesto inexistente
- **WHEN** un ítem referencia un repuesto inexistente
- **THEN** responde 404

### Requirement: Catálogo de estados no vacío
El sistema SHALL responder 409 si no existe ningún estado en `estado_orden` al intentar abrir una orden (RN-19).

#### Scenario: Catálogo vacío
- **WHEN** se intenta abrir una orden con el catálogo `estado_orden` vacío
- **THEN** responde 409

### Requirement: Línea inicial de historial de estado
El sistema SHALL registrar en `historial_estado_orden` una línea con `desde_estado=NULL`, `hasta_estado='PENDIENTE'`, `usuario_id` del creador y `cuando` en la misma transacción de apertura.

#### Scenario: Historial inicial creado
- **WHEN** se abre una orden válida
- **THEN** existe una línea en `historial_estado_orden` con `desde_estado` nulo y `hasta_estado` PENDIENTE

### Requirement: Consulta de orden por id con precarga
El sistema SHALL devolver una orden por id con `vehiculo`, `items.repuesto` y `mecanico` precargados mediante `selectinload` (sin N+1). Un id inexistente MUST responder 404. Un usuario sin permiso (no RECEPCION/ADMIN, no mecánico asignado, no dueño del vehículo) MUST responder 403.

#### Scenario: Detalle con precarga
- **WHEN** se consulta una orden existente con permiso
- **THEN** responde 200 incluyendo `vehiculo`, `items` con `repuesto` y `mecanico`

#### Scenario: Orden inexistente
- **WHEN** se consulta un id inexistente
- **THEN** responde 404

#### Scenario: Sin permiso
- **WHEN** un usuario sin permiso consulta la orden
- **THEN** responde 403

### Requirement: Listado paginado de órdenes filtrado por estado
El sistema SHALL exponer `GET /ordenes` con filtro opcional `estado` y paginación `page`/`size`, para usuarios con rol RECEPCION, MECANICO o ADMIN, devolviendo órdenes con precarga de `vehiculo`, `items.repuesto` y `mecanico`.

#### Scenario: Listado exitoso
- **WHEN** un usuario autorizado solicita GET /ordenes
- **THEN** responde 200 con una página de órdenes

#### Scenario: Filtro por estado
- **WHEN** se envía `estado=PENDIENTE`
- **THEN** la respuesta contiene solo órdenes en ese estado

#### Scenario: Paginación inválida
- **WHEN** `page` o `size` son inválidos
- **THEN** responde 422

#### Scenario: Sin rol suficiente
- **WHEN** un usuario sin rol RECEPCION/MECANICO/ADMIN invoca GET /ordenes
- **THEN** responde 403

### Requirement: Consulta de órdenes propias
El sistema SHALL exponer `GET /mis-ordenes` que devuelve únicamente las órdenes cuyo vehículo pertenece al cliente del usuario autenticado (RN-17), con paginación. Un usuario sin rol CLIENTE MUST recibir 403.

#### Scenario: Cliente ve solo sus órdenes
- **WHEN** un cliente autenticado consulta /mis-ordenes
- **THEN** la respuesta contiene solo las órdenes de sus vehículos

#### Scenario: Sin rol CLIENTE
- **WHEN** un usuario sin rol CLIENTE invoca /mis-ordenes
- **THEN** responde 403

### Requirement: Catálogo de estados ordenado por posición
El sistema SHALL exponer `GET /estados-orden` que devuelve el catálogo de estados ordenado por `posicion` ascendente.

#### Scenario: Orden por posición
- **WHEN** se consulta GET /estados-orden
- **THEN** los estados se devuelven ordenados por `posicion` ascendente
