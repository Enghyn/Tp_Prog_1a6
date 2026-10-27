# Propuesta

## ¿Por qué?

La API necesita un contrato unificado para la validación de solicitudes, las respuestas de error y la paginación. Actualmente no existe un manejo estandarizado de errores ni un patrón de paginación, lo que generaría comportamientos inconsistentes entre módulos. Este cambio establece convenciones transversales que todos los endpoints futuros deben seguir.

## ¿Qué cambios?

- **Sistema de errores**: Crear `app/core/errors.py` con `ErrorAplicacion` base y excepciones de dominio (`ConflictoError`, `NoEncontradoError`, `ProhibidoError`, `NoAutenticadoError`, `ReglaNegocioError`, `DemasiadasPeticionesError` con `reintentar_despues`)
- **Manejadores de excepciones**: Añadir manejadores en `main.py` mapeando excepciones a códigos HTTP (400/401/403/404/409/422/429) con cuerpo uniforme `{"detail", "codigo"}` y header `Retry-After` cuando corresponda
- **Traducción de IntegrityError**: Traducir `IntegrityError` (UNIQUE/FK) a 409 con mensaje de dominio, sin exponer nombres de restricciones ni trazas (RN-18)
- **Errores de validación**: Traducir `RequestValidationError` a 422 con lista de campos
- **Paginación**: Crear `app/core/paginacion.py` con `ParametrosPagina` y `Pagina[T]` genérico
- **Convenciones de esquemas**: Aplicar `extra="forbid"` en todos los esquemas de entrada, normalización de strings (`strip`) y `EmailStr`

## Capacidades

### Nuevas Capacidades
- `http-contracts`: Contratos HTTP unificados para errores, validación y paginación en toda la API

### Capacidades Modificadas
<!-- Sin capacidades existentes para modificar -->

## Impacto

**Áreas afectadas:**
- `app/core/errors.py` (nuevo)
- `app/core/paginacion.py` (nuevo)
- `main.py` (manejadores de excepciones)
- Todos los esquemas de entrada futuros deben seguir las convenciones

**Dependencias:** C-01 (foundation-setup)

**Notas:**
- Debe seguir RN-01, RN-10, RN-18
- Las respuestas de error nunca deben exponer detalles internos
- Todos los esquemas de entrada deben rechazar campos extra
