# Tareas

## 1. Sistema de errores
- [x] 1.1 Crear `app/core/errors.py` con clase base `ErrorAplicacion` y todas las excepciones de dominio (`ConflictoError`, `NoEncontradoError`, `ProhibidoError`, `NoAutenticadoError`, `ReglaNegocioError`, `DemasiadasPeticionesError`) con `reintentar_despues` opcional - Verificar: todas las clases definidas correctamente
- [x] 1.2 Añadir manejadores de excepciones en `main.py` para `ErrorAplicacion`, `RequestValidationError` e `IntegrityError` mapeando a códigos HTTP correctos con formato uniforme `{"detail", "codigo"}` y header `Retry-After` cuando corresponda - Verificar: manejadores registrados y retornan formato correcto

## 2. Paginación
- [x] 2.1 Crear `app/core/paginacion.py` con `ParametrosPagina` (pagina >= 1, tamanio 1-100, valores por defecto) y modelo genérico `Pagina[T]` - Verificar: modelos validan correctamente y se serializan bien

## 3. Convenciones de esquemas
- [x] 3.1 Documentar convenciones para esquemas de entrada (extra="forbid", strip, EmailStr) para uso en todo el proyecto - Verificar: convenciones claras y aplicables

## 4. Pruebas
- [x] 4.1 Crear pruebas para manejo de errores: campo extra retorna 422, IntegrityError simulado retorna 409 sin detalles internos, formato uniforme de error - Verificar: todas las pruebas de errores pasan
- [x] 4.2 Crear pruebas para paginación: `Pagina[T]` se serializa correctamente con total/pagina - Verificar: pruebas de paginación pasan
