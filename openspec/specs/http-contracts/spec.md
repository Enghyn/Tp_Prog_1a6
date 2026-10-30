# Especificación: http-contracts

## Purpose

Establece un contrato unificado para respuestas de error HTTP, validación de solicitudes y paginación que todos los endpoints de la API deben seguir.

## Requirements

### Requirement: Excepciones de dominio
El sistema SHALL proveer clases de error de dominio (`ErrorAplicacion`, `ConflictoError`, `NoEncontradoError`, `ProhibidoError`, `NoAutenticadoError`, `ReglaNegocioError`, `DemasiadasPeticionesError`) con soporte para `reintentar_despues` en errores de límite de peticiones.

#### Scenario: Error de límite de peticiones con reintento
- **CUANDO** se lanza `DemasiadasPeticionesError` con `reintentar_despues` configurado
- **ENTONCES** la excepción contiene la información de reintento para uso por los manejadores

### Requirement: Formato uniforme de respuesta de error
El sistema SHALL retornar todos los errores en el formato `{"detail", "codigo"}` con los códigos HTTP apropiados (400, 401, 403, 404, 409, 422, 429) e incluir el header `Retry-After` cuando corresponda.

#### Scenario: Mapeo de errores de dominio
- **CUANDO** se lanza cualquier subclase de `ErrorAplicacion`
- **ENTONCES** el sistema retorna el código HTTP correspondiente con el cuerpo de error uniforme

### Requirement: Traducción de errores de integridad
El sistema SHALL traducir `IntegrityError` de la base de datos (violaciones UNIQUE/FK) a HTTP 409 con mensajes de dominio, sin exponer nombres de restricciones ni trazas de error.

#### Scenario: Violación de clave duplicada
- **CUANDO** ocurre un `IntegrityError` por violación de restricción UNIQUE
- **ENTONCES** el sistema retorna HTTP 409 con un mensaje de dominio apropiado y sin detalles internos

### Requirement: Errores de validación de solicitudes
El sistema SHALL traducir `RequestValidationError` a HTTP 422 con la lista de errores de validación.

#### Scenario: Cuerpo de solicitud inválido
- **CUANDO** falla la validación de la solicitud
- **ENTONCES** el sistema retorna HTTP 422 con los detalles de los errores de validación

### Requirement: Soporte de paginación
El sistema SHALL proveer `ParametrosPagina` para parámetros de consulta (`pagina >= 1`, `tamanio` entre 1 y 100 con valores por defecto) y un modelo genérico `Pagina[T]`.

#### Scenario: Respuesta paginada
- **CUANDO** se retornan datos paginados
- **ENTONCES** la respuesta incluye los campos `items`, `total`, `pagina` y `tamanio`

### Requirement: Convenciones para esquemas de entrada
Todos los esquemas de entrada SHALL usar `model_config = ConfigDict(extra="forbid")` para rechazar campos extra, normalizar strings con `strip`, y usar `EmailStr` para campos de correo electrónico.

#### Scenario: Campo extra rechazado
- **CUANDO** una solicitud contiene campos no declarados en el esquema
- **ENTONCES** el sistema retorna HTTP 422 por error de validación
