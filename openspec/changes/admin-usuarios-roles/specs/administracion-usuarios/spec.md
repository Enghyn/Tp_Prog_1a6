# Spec Delta

## Purpose

Defines how an administrator onboards staff and manages role assignments, including the historical audit of every assignment and the self-protection rules that keep the system administrable.

## ADDED Requirements

### Requirement: Superficie de administración de usuarios restringida a ADMIN

Las rutas `POST /usuarios`, `GET /usuarios/{id}/roles`, `POST /usuarios/{id}/roles` y `DELETE /usuarios/{id}/roles/{rol}` SHALL exigir una sesión válida y un rol `ADMIN` vigente leído de `asignacion_rol` en la misma petición.

#### Scenario: Petición sin sesión

- **WHEN** se invoca cualquiera de las rutas de administración de usuarios sin cookie `access_token`
- **THEN** la respuesta es `401` con `codigo = "CREDENCIALES_INVALIDAS"` y ningún cambio se persiste

#### Scenario: Sesión válida sin rol ADMIN

- **WHEN** un usuario autenticado con roles vigentes `RECEPCION` o `MECANICO` invoca una ruta de administración de usuarios
- **THEN** la respuesta es `403` con `codigo = "PERMISOS_INSUFICIENTES"`

#### Scenario: Rol ADMIN revocado en caliente

- **WHEN** un administrador cuyo rol `ADMIN` fue revocado después de emitir su token invoca una ruta de administración de usuarios
- **THEN** la respuesta es `403`, aunque su token siga sin expirar y contenga `ADMIN` en sus claims

#### Scenario: Contraseña provisoria pendiente bloquea la operación

- **WHEN** un administrador con `debe_cambiar_password = True` invoca una ruta de administración de usuarios
- **THEN** la respuesta es `403` con `codigo = "CAMBIO_PASSWORD_REQUERIDO"` y la operación no se ejecuta

### Requirement: Alta de personal con contraseña provisoria

`POST /usuarios` SHALL crear un usuario activo a partir de `email`, `nombre` y `password`, almacenando sólo el hash bcrypt de la contraseña y marcando `debe_cambiar_password = True`; el email se normaliza a minúsculas y sin espacios antes de persistirse.

#### Scenario: Alta exitosa

- **WHEN** un administrador envía `{"email": "Nuevo.Mecanico@Taller.local", "nombre": "Nuevo Mecánico", "password": "Provisoria1"}`
- **THEN** la respuesta es `201` con el `id`, `email = "nuevo.mecanico@taller.local"`, `nombre`, `activo = true` y `debe_cambiar_password = true`, y la contraseña almacenada no es igual al texto recibido pero verifica contra él

#### Scenario: La contraseña provisoria no se devuelve

- **WHEN** se completa un alta de personal
- **THEN** el cuerpo de la respuesta no contiene `password`, `password_hash` ni ningún valor derivado del hash

#### Scenario: El usuario creado puede iniciar sesión con la contraseña provisoria

- **WHEN** el usuario recién creado envía sus credenciales a `POST /auth/login`
- **THEN** el login responde `200` y la sesión devuelta incluye `debe_cambiar_password = true` sin roles asignados

### Requirement: Rechazo de alta con email duplicado

`POST /usuarios` SHALL rechazar con `409` un email que ya pertenezca a otro usuario, sin crear un segundo usuario ni alterar el existente, y sin exponer nombres de constraints ni trazas.

#### Scenario: Email ya registrado

- **WHEN** un administrador intenta dar de alta un email que ya existe, con distinta capitalización
- **THEN** la respuesta es `409` con `codigo = "EMAIL_DUPLICADO"` y la cantidad de usuarios con ese email sigue siendo uno

#### Scenario: La respuesta de conflicto no revela el esquema

- **WHEN** se rechaza un alta por email duplicado
- **THEN** el cuerpo de la respuesta no contiene `usuario_email_key`, `ix_usuario_email`, nombres de tablas ni fragmentos de SQL

#### Scenario: El conflicto no deja un evento de alta

- **WHEN** el alta falla por email duplicado
- **THEN** no se registra ningún evento `USUARIO_CREADO` para ese intento

### Requirement: Contrato estricto del alta de personal

`POST /usuarios` SHALL aceptar exclusivamente `email`, `nombre` y `password`; cualquier campo adicional, email inválido, nombre vacío, contraseña de menos de 8 o más de 72 caracteres, o contraseña sin mayúscula, minúscula y dígito SHALL responder `422` sin crear el usuario.

#### Scenario: Campo extra en el cuerpo

- **WHEN** se envía `{"email": "...", "nombre": "...", "password": "...", "activo": false}`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"` y el campo `activo` señalado en `detail[].loc`

#### Scenario: Email con formato inválido

- **WHEN** se envía `email = "nuevo-taller.local"`
- **THEN** la respuesta es `422` y no se crea ningún usuario

#### Scenario: Contraseña provisoria débil

- **WHEN** se envía una `password` de 7 caracteres, o sin dígito, o sin mayúscula
- **THEN** la respuesta es `422` y no se crea ningún usuario

#### Scenario: La validación no repite la contraseña

- **WHEN** la respuesta es `422` por contraseña inválida
- **THEN** el cuerpo del error no incluye el valor de `password` recibido

### Requirement: Historial de roles de un usuario

`GET /usuarios/{id}/roles` SHALL devolver todas las asignaciones del usuario, vigentes y revocadas, ordenadas por `desde` descendente, incluyendo para cada una su `rol`, `desde`, `vence_en`, `revocada_en` y una marca `vigente` calculada al momento de la consulta.

#### Scenario: Usuario con asignaciones históricas

- **WHEN** un administrador consulta los roles de un usuario que tuvo `MECANICO` revocado y luego `RECEPCION` vigente
- **THEN** la respuesta es `200` con las dos asignaciones ordenadas por `desde` descendente, ambas con su `revocada_en` correspondiente y sólo la de `RECEPCION` con `vigente = true`

#### Scenario: Asignación vencida no figura como vigente

- **WHEN** el usuario tiene una única asignación con `vence_en` en el pasado y `revocada_en = null`
- **THEN** la respuesta es `200` con esa asignación y `vigente = false`

#### Scenario: Usuario sin asignaciones

- **WHEN** un administrador consulta los roles de un usuario que nunca tuvo roles
- **THEN** la respuesta es `200` con la lista de asignaciones vacía

#### Scenario: Usuario inexistente

- **WHEN** un administrador consulta los roles de un `id` que no existe
- **THEN** la respuesta es `404` con `codigo = "USUARIO_NO_ENCONTRADO"`

### Requirement: Asignación de rol con vencimiento opcional

`POST /usuarios/{id}/roles` SHALL crear una asignación abierta con `desde` igual al instante de la petición, `otorgada_por` igual al `id` del administrador autenticado y `vence_en` opcional; responderá `201` con la asignación creada.

#### Scenario: Asignación sin vencimiento

- **WHEN** un administrador envía `{"rol": "RECEPCION"}` para un usuario existente sin ese rol
- **THEN** la respuesta es `201` con `rol = "RECEPCION"`, `vence_en = null`, `revocada_en = null` y `otorgada_por` igual al `id` del administrador autenticado

#### Scenario: Asignación con vencimiento futuro

- **WHEN** un administrador envía `{"rol": "MECANICO", "vence_en": "<instante futuro>"}`
- **THEN** la respuesta es `201` y la asignación queda con ese `vence_en` tal cual se envió, sin truncar zonas horarias

#### Scenario: La asignación habilita la autorización en la petición siguiente

- **WHEN** un administrador asigna `RECEPCION` a un usuario que luego invoca una ruta que exige `RECEPCION` con el mismo token previo
- **THEN** esa ruta responde con éxito, sin reemitir el token

#### Scenario: Usuario inexistente

- **WHEN** se intenta asignar un rol a un `id` de usuario que no existe
- **THEN** la respuesta es `404` con `codigo = "USUARIO_NO_ENCONTRADO"` y no se crea ninguna asignación

### Requirement: Rechazo de doble asignación vigente

`POST /usuarios/{id}/roles` SHALL responder `409` cuando el usuario ya tenga una asignación abierta y vigente del mismo rol (RN-03), sin crear una segunda fila.

#### Scenario: Rol vigente duplicado

- **WHEN** un administrador asigna `RECEPCION` a un usuario cuya asignación `RECEPCION` sigue vigente
- **THEN** la respuesta es `409` con `codigo = "ROL_YA_ASIGNADO"` y el usuario conserva una sola asignación abierta de ese rol

#### Scenario: El conflicto no altera la asignación existente

- **WHEN** el intento de doble asignación es rechazado
- **THEN** el `desde` y el `vence_en` de la asignación original no cambian

### Requirement: Reasignación de un rol vencido

`POST /usuarios/{id}/roles` SHALL cerrar la asignación abierta cuyo `vence_en` ya pasó, fijando su `revocada_en` en el instante de la petición, y abrir una fila nueva para el mismo rol.

#### Scenario: Rol vencido se reasigna

- **WHEN** un administrador asigna `MECANICO` a un usuario cuya única asignación `MECANICO` tiene `vence_en` en el pasado y `revocada_en = null`
- **THEN** la respuesta es `201`, la fila anterior queda con `revocada_en` no nulo y existe una segunda fila `MECANICO` con `revocada_en = null` y `vence_en` según la solicitud

#### Scenario: El historial conserva las dos filas

- **WHEN** se reasigna un rol vencido y luego se consulta `GET /usuarios/{id}/roles`
- **THEN** la respuesta incluye las dos asignaciones del rol, la cerrada con su `revocada_en` y la nueva como `vigente = true`

### Requirement: Revocación lógica de un rol

`DELETE /usuarios/{id}/roles/{rol}` SHALL fijar `revocada_en` en el instante de la petición sobre la asignación abierta, sin borrar la fila, y responder `200`; la autorización derivada de ese rol SHALL cesar en la petición siguiente.

#### Scenario: Revocación exitosa

- **WHEN** un administrador revoca `RECEPCION` de un usuario que lo tenía vigente
- **THEN** la respuesta es `200`, la fila conserva su `desde` original y queda con `revocada_en` no nulo

#### Scenario: El rol revocado deja de autorizar de inmediato

- **WHEN** el usuario revocado invoca una ruta que exige `RECEPCION` con el mismo token previo
- **THEN** la respuesta es `403` con `codigo = "PERMISOS_INSUFICIENTES"`

#### Scenario: Revocación de un rol no vigente

- **WHEN** se revoca un rol que el usuario nunca tuvo, o cuya asignación ya está revocada o vencida
- **THEN** la respuesta es `404` con `codigo = "ASIGNACION_NO_ENCONTRADA"` y ninguna fila se modifica

#### Scenario: Rol fuera del catálogo

- **WHEN** se invoca la revocación con un `rol` distinto de `ADMIN`, `RECEPCION`, `MECANICO` o `CLIENTE`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"`

#### Scenario: Usuario inexistente

- **WHEN** se revoca un rol de un `id` de usuario que no existe
- **THEN** la respuesta es `404` con `codigo = "USUARIO_NO_ENCONTRADO"`

### Requirement: Rechazo de asignación con rol o vencimiento inválidos

`POST /usuarios/{id}/roles` SHALL aceptar exclusivamente `rol` y `vence_en`, responder `422` si `rol` no pertenece al catálogo o si `vence_en` no es un instante futuro, y no crear ninguna asignación en esos casos.

#### Scenario: Rol desconocido

- **WHEN** un administrador envía `{"rol": "GERENTE"}`
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"` y no se crea ninguna asignación

#### Scenario: Vencimiento en el pasado

- **WHEN** un administrador envía un `vence_en` anterior al instante de la petición
- **THEN** la respuesta es `422` con `codigo = "ERROR_VALIDACION"` y no se crea ninguna asignación

#### Scenario: Campo extra en el cuerpo

- **WHEN** se envía `{"rol": "MECANICO", "otorgada_por": 1}`
- **THEN** la respuesta es `422` y `otorgada_por` no puede ser fijado por el cliente

### Requirement: Prohibición de revocar el propio rol ADMIN

`DELETE /usuarios/{id}/roles/ADMIN` SHALL responder `409` cuando el `id` destino sea el del administrador autenticado, y la asignación SHALL permanecer vigente.

#### Scenario: Administrador intenta revocar su propio ADMIN

- **WHEN** un administrador autenticado revoca `ADMIN` sobre su propio `id`
- **THEN** la respuesta es `409` con `codigo = "AUTOPROTECCION_ADMIN"` y su asignación `ADMIN` sigue vigente

#### Scenario: Revocar un rol propio distinto de ADMIN

- **WHEN** un administrador que también tiene `MECANICO` vigente revoca su propio `MECANICO`
- **THEN** la respuesta es `200` y su rol `ADMIN` no se altera

### Requirement: Prohibición de dejar el sistema sin administradores vigentes

`DELETE /usuarios/{id}/roles/ADMIN` SHALL responder `409` cuando la revocación dejaría el sistema sin ninguna asignación `ADMIN` vigente, contando `revocada_en IS NULL` y `vence_en` nulo o futuro.

#### Scenario: Último administrador vigente

- **WHEN** un administrador revoca `ADMIN` de otro usuario cuando esa es la única asignación `ADMIN` vigente del sistema y la suya propia no existe
- **THEN** la respuesta es `409` con `codigo = "ULTIMO_ADMIN"` y la asignación permanece vigente

#### Scenario: Un ADMIN vencido no cuenta como vigente

- **WHEN** el sistema tiene un `ADMIN` vigente y otro con `vence_en` en el pasado, y se revoca el vigente
- **THEN** la respuesta es `409` con `codigo = "ULTIMO_ADMIN"`

#### Scenario: Con dos administradores vigentes la revocación procede

- **WHEN** existen dos asignaciones `ADMIN` vigentes y un administrador revoca la del otro usuario
- **THEN** la respuesta es `200` y queda exactamente una asignación `ADMIN` vigente

### Requirement: Auditoría de las operaciones de administración

Cada operación exitosa de administración SHALL registrar un evento en `evento_seguridad` con `actor` igual al email del administrador autenticado y `accion` igual a `USUARIO_CREADO`, `ROL_ASIGNADO` o `ROL_REVOCADO` según corresponda.

#### Scenario: Alta de personal auditada

- **WHEN** un administrador crea un usuario
- **THEN** existe un evento con `accion = "USUARIO_CREADO"` y `actor` igual al email de ese administrador

#### Scenario: Asignación auditada

- **WHEN** un administrador asigna un rol
- **THEN** existe un evento con `accion = "ROL_ASIGNADO"` y `actor` igual al email de ese administrador

#### Scenario: Revocación auditada

- **WHEN** un administrador revoca un rol
- **THEN** existe un evento con `accion = "ROL_REVOCADO"` y `actor` igual al email de ese administrador

#### Scenario: Los rechazos no generan eventos de éxito

- **WHEN** una operación de administración responde `403`, `404`, `409` o `422`
- **THEN** no se registra el evento `USUARIO_CREADO`, `ROL_ASIGNADO` ni `ROL_REVOCADO` de esa operación
