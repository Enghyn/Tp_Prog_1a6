# Diseño

## Contexto

C-01 estableció la base. C-02 construye sobre ella para crear contratos HTTP transversales que seguirán todos los endpoints futuros.

## Objetivos / No Objetivos

**Objetivos:**
- Crear un sistema unificado de manejo de errores
- Establecer respuestas consistentes para errores de validación
- Proveer utilidades de paginación
- Definir convenciones para esquemas de entrada

**No Objetivos:**
- Manejo de errores específico por módulo
- Detalles de errores de autenticación más allá de la estructura (se manejan en C-09)
- Páginas de error personalizadas

## Decisiones

### Decisión 1: Jerarquía de excepciones
**Opción elegida:** Crear clase base `ErrorAplicacion` con subclases para cada tipo de error HTTP
**Justificación:** Permite manejo centralizado en los manejadores manteniendo el significado semántico

### Decisión 2: Formato uniforme de error
**Opción elegida:** Todos los errores retornan `{"detail": "...", "codigo": "CODIGO_ERROR"}`
**Justificación:** Provee un contrato API consistente para que los clientes puedan parsear errores programáticamente

### Decisión 3: Traducción de IntegrityError
**Opción elegida:** Capturar `IntegrityError` de SQLAlchemy y traducirlo a 409 con mensajes de dominio, ocultando detalles de restricciones
**Justificación:** Seguridad (RN-18) - evita filtrar información del esquema de base de datos

### Decisión 4: Paginación como utilidad central
**Opción elegida:** `Pagina[T]` y `ParametrosPagina` en `app/core/`
**Justificación:** Usado en múltiples módulos (clientes, repuestos, ordenes) según la base de conocimiento

### Decisión 5: Validación estricta de entrada
**Opción elegida:** `extra="forbid"` en todos los esquemas de entrada
**Justificación:** Previene campos inesperados y detecta errores del cliente tempranamente

## Riesgos / Compromisos

- **Riesgo:** Validación demasiado estricta que limite flexibilidad → **Mitigación:** Aplicar solo a esquemas de entrada, no a esquemas de respuesta
- **Riesgo:** Ocultar detalles de IntegrityError dificulta depuración → **Mitigación:** Registrar internamente con detalles completos, retornar mensajes sanitizados
- **Compromiso:** Más código para esquemas, pero garantiza consistencia
