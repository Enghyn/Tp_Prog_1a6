# Spec Delta

## ADDED Requirements

### Requirement: Cambio de contraseña autenticado

`POST /auth/cambiar-password` SHALL exigir una sesión válida y aceptar únicamente `password_actual` y `password_nueva`. Con la contraseña actual correcta y una nueva que cumpla la política, SHALL responder `200`, persistir el nuevo hash, fijar `password_cambiada_en` con microsegundos y `debe_cambiar_password=false`, sin reemitir la cookie de sesión (RN-06, RN-07).

#### Scenario: Cambio exitoso persiste el nuevo estado

- **WHEN** un usuario autenticado envía su contraseña actual correcta y una contraseña nueva válida
- **THEN** el sistema responde `200`, el `password_hash` almacenado verifica contra la nueva contraseña, `password_cambiada_en` queda en el instante del cambio sin truncar microsegundos y `debe_cambiar_password` queda en `false`

#### Scenario: La respuesta no reemite la cookie de sesión

- **WHEN** el cambio de contraseña es exitoso
- **THEN** la respuesta `200` no incluye un `Set-Cookie` con un token nuevo, porque el token usado para la petición queda inválido por RN-07

#### Scenario: Usuario con contraseña provisoria puede cambiar

- **WHEN** un usuario con `debe_cambiar_password=true` invoca el endpoint con una cookie válida
- **THEN** la petición se procesa (no responde `403`) y, si el cambio es exitoso, la bandera queda en `false`

#### Scenario: El token anterior deja de ser válido

- **WHEN** el usuario cambia su contraseña y luego reutiliza el token con el que hizo la petición
- **THEN** el sistema responde `401` en la siguiente petición protegida, porque su `iat` es anterior a `password_cambiada_en`

#### Scenario: Un token emitido después del cambio es válido

- **WHEN** el usuario vuelve a autenticarse con la contraseña nueva y usa el token recién emitido
- **THEN** la petición protegida se procesa normalmente

### Requirement: Rechazo del cambio de contraseña

El sistema SHALL responder `401` uniforme cuando `password_actual` no verifica, sin persistir ningún cambio. SHALL responder `422` cuando falte un campo, se envíe un campo no declarado, `password_nueva` quede fuera de 8–72 caracteres, no incluya mayúscula, minúscula y dígito, o sea igual a `password_actual`.

#### Scenario: Contraseña actual incorrecta

- **WHEN** el usuario envía una `password_actual` que no verifica contra su hash
- **THEN** el sistema responde `401` con el cuerpo y código uniformes de credenciales inválidas, y el hash, `password_cambiada_en` y `debe_cambiar_password` permanecen sin cambios

#### Scenario: Contrato de entrada estricto

- **WHEN** el cuerpo omite `password_actual` o `password_nueva`, o incluye un campo no declarado
- **THEN** el sistema responde `422` con el formato uniforme de error y no modifica la contraseña

#### Scenario: Longitud fuera de rango

- **WHEN** `password_nueva` tiene menos de 8 o más de 72 caracteres
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: Complejidad insuficiente

- **WHEN** `password_nueva` no contiene al menos una mayúscula, una minúscula y un dígito
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: La contraseña nueva repite la actual

- **WHEN** `password_nueva` es igual a `password_actual`
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: Petición sin sesión

- **WHEN** se invoca el endpoint sin cookie `access_token` válida
- **THEN** el sistema responde `401` antes de evaluar el cuerpo

#### Scenario: La respuesta 422 no repite las contraseñas

- **WHEN** el cuerpo del cambio de contraseña falla la validación
- **THEN** la respuesta `422` lista los campos y mensajes de error sin incluir `password_actual` ni `password_nueva` en el cuerpo

## MODIFIED Requirements

### Requirement: Auditoría de acceso en transacción independiente

El sistema SHALL registrar cada intento de login en `intento_acceso` y cada evento de seguridad en `evento_seguridad` (`LOGIN_OK`, `LOGIN_FALLIDO`, `LOGIN_BLOQUEADO`, `LOGOUT`, `PASSWORD_CAMBIADA`) dentro de una transacción independiente que SHALL confirmarse aunque la petición termine en error.

#### Scenario: Login fallido deja rastro persistido

- **WHEN** un login falla por credenciales inválidas
- **THEN** el intento queda persistido con `exito=false` y el evento `LOGIN_FALLIDO` queda registrado, pese a que la petición responde `401`

#### Scenario: Login exitoso auditado

- **WHEN** un login es exitoso
- **THEN** se persiste un intento con `exito=true` y el evento `LOGIN_OK`

#### Scenario: Bloqueo auditado sin sumar fallos

- **WHEN** una petición es rechazada por límite de intentos
- **THEN** se registra el evento `LOGIN_BLOQUEADO` y no se inserta un nuevo intento fallido

#### Scenario: Logout auditado

- **WHEN** el logout identifica una sesión válida
- **THEN** se registra el evento `LOGOUT` con el usuario como actor

#### Scenario: Cambio de contraseña auditado

- **WHEN** un cambio de contraseña es exitoso
- **THEN** se registra el evento `PASSWORD_CAMBIADA` con el email del usuario como actor y el instante del cambio, sin insertar una fila en `intento_acceso`
