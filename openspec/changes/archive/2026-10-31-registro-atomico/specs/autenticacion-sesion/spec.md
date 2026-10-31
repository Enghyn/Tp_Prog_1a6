# Spec Delta

## ADDED Requirements

### Requirement: Auto-registro público atómico

`POST /auth/registro` SHALL ser público y aceptar `email`, `nombre`, `password`, `documento` y `telefono`. SHALL calcular el hash de la contraseña antes de abrir la transacción y, dentro de un único `UnitOfWork`, crear `Usuario` (activo, sin contraseña provisoria), `AsignacionRol` con rol `CLIENTE` vigente y `Cliente` vinculado al usuario, confirmando o revirtiendo las tres escrituras en bloque (RN-02).

#### Scenario: Alta exitosa

- **WHEN** un visitante envía un registro válido con email y documento nuevos
- **THEN** el sistema responde `201` con el usuario creado (sin `password_hash`) y el cliente asociado, y las tres entidades quedan persistidas

#### Scenario: Login inmediato tras el registro

- **WHEN** un registro fue exitoso
- **THEN** el usuario puede autenticarse inmediatamente con el email y la contraseña enviados y obtener una sesión válida

#### Scenario: Evento de seguridad registrado

- **WHEN** el registro se confirma
- **THEN** queda una fila en `evento_seguridad` con `accion = "USUARIO_AUTO_REGISTRADO"` y el email del nuevo usuario como `actor`, dentro de la misma transacción

### Requirement: Contrato de entrada del auto-registro

`POST /auth/registro` SHALL rechazar con `422` cuando falte un campo obligatorio, se envíe un campo no declarado, el email no sea válido, la contraseña quede fuera de 8–72 caracteres o no incluya mayúscula, minúscula y dígito, o `nombre`, `documento` o `telefono` queden vacíos o superen sus límites.

#### Scenario: Campo extra rechazado

- **WHEN** el cuerpo incluye un campo no declarado
- **THEN** el sistema responde `422` con `codigo = "ERROR_VALIDACION"` y no persiste ninguna entidad

#### Scenario: Contraseña inválida

- **WHEN** la contraseña tiene menos de 8 caracteres o carece de mayúscula, minúscula o dígito
- **THEN** el sistema responde `422` y no persiste ninguna entidad

### Requirement: Duplicado de email o documento sin residuos

Si el email ya está registrado o el documento ya existe, `POST /auth/registro` SHALL responder `409` con `codigo = "EMAIL_DUPLICADO"` o `codigo = "DOCUMENTO_DUPLICADO"` respectivamente, sin dejar `Usuario`, `AsignacionRol` ni `Cliente` huérfanos.

#### Scenario: Email duplicado

- **WHEN** se registra un usuario con un email ya existente
- **THEN** el sistema responde `409` con `codigo = "EMAIL_DUPLICADO"` y las tres tablas quedan sin nuevas filas para ese intento

#### Scenario: Documento duplicado

- **WHEN** se registra un cliente con un documento ya existente
- **THEN** el sistema responde `409` con `codigo = "DOCUMENTO_DUPLICADO"` y las tres tablas quedan sin nuevas filas para ese intento

### Requirement: Rollback total ante fallo parcial

Si falla la creación de cualquiera de las tres entidades (incluyendo la violación de una restricción única), el `UnitOfWork` SHALL revertir todas las escrituras previas, de modo que queden 0 filas nuevas en `usuario`, `asignacion_rol` y `cliente` para ese intento.

#### Scenario: Fallo al crear el cliente revierte usuario y rol

- **WHEN** la creación del `Cliente` falla (por ejemplo, documento duplicado) después de haber creado el `Usuario` y el `AsignacionRol`
- **THEN** no queda ninguna fila nueva en `usuario`, `asignacion_rol` ni `cliente` para ese intento

### Requirement: Concurrencia de registros con el mismo email

Ante dos registros concurrentes con el mismo email, las restricciones únicas de base de datos SHALL garantizar que sólo uno persista; el otro SHALL responder `409` con `codigo = "EMAIL_DUPLICADO"` sin residuos.

#### Scenario: Dos registros concurrentes, uno solo persiste

- **WHEN** dos peticiones de registro con el mismo email se procesan concurrentemente
- **THEN** exactamente uno responde `201` y el otro `409`, y no quedan filas huérfanas ni duplicadas