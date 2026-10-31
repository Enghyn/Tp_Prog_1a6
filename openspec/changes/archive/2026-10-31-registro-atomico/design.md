# Design

## Context

Ver `proposal.md` - Why. Los módulos `app/modules/usuarios/` y `app/modules/clientes/` ya contienen modelos, repositorios y sus `UnitOfWork` (C-13, C-14, C-15 archivados). Las tablas e índices únicos (`usuario.email`, `cliente.documento`, `uq_cliente_usuario`) existen desde C-06/C-07. No hay cambios de schema.

## Goals / Non-Goals

**Goals:**
- Exponer `POST /auth/registro` público con escritura atómica de las tres entidades (RN-02).
- Calcular el hash de contraseña fuera de la transacción (no retener conexión durante bcrypt).
- Garantizar `409` por email o documento duplicado sin huérfanos, `422` por contrato inválido y `201` sin `password_hash`.
- Registrar `USUARIO_AUTO_REGISTRADO` en la misma transacción (rollback en fallo).
- Soportar concurrencia por email vía restricciones únicas de BD.

**Non-Goals:**
- Verificación de email, CAPTCHA o políticas de contraseña distintas a las ya definidas.
- Migración Alembic ni cambios de modelo.
- Reutilización de `UsuariosUnitOfWork`/`ClientesUnitOfWork` por separado (se compone uno dedicado).

## Decisions

1. **UnitOfWork dedicado (`RegistroUnitOfWork`)**: se agrega en `app/modules/usuarios/unit_of_work.py` y compone `UsuarioRepository`, `AsignacionRolRepository`, `EventoSeguridadRepository` (usuarios) y `ClienteRepository` (clientes) sobre una sola sesión.  
   *Alternativa*: usar `UsuariosUnitOfWork` + `ClientesUnitOfWork` sobre la misma sesión → riesgo de dos puntos de commit/rollback y doble ownership. Rechazada.

2. **Servicio en `usuarios/service.py`**: nueva función `registrar_cliente(solicitud, app_state, sesion)` que recibe la sesión del request, hashea primero y luego abre `async with RegistroUnitOfWork(sesion)`.  
   *Justificación*: el endpoint vive en el módulo de autenticación y el flujo es público; mantener el service junto al resto de auth.

3. **Hash antes de la transacción**: `password_hash = await hash_password(..., app_state)` se ejecuta antes del bloque `async with`, de modo que bcrypt no retiene la conexión.

4. **Rol `CLIENTE` auto-asignado**: `crear_asignacion` con `rol="CLIENTE"`, `desde=now`, `vence_en=None`, `otorgada_por=None` (auto-registro, sin administrador).

5. **Cliente vinculado**: se crea con `usuario_id=usuario.id`, `nombre`, `documento`, `telefono`. `debe_cambiar_password=False` en el usuario (la contraseña la eligió el propio usuario).

6. **Detección de duplicados**: pre-chequeo por email (`buscar_usuario_por_email`) y por documento (consulta directa) → `ConflictoError` con `EMAIL_DUPLICADO`/`DOCUMENTO_DUPLICADO`. Además, cada `flush()` se envuelve en `try/except IntegrityError` para traducir la carrera concurrente al mismo código.

7. **Auditoría en la misma transacción**: `registrar_evento(..., accion="USUARIO_AUTO_REGISTRADO")` dentro del bloque; si la transacción revierte, el evento también se revierte (no se audita un registro fallido).

8. **Respuesta**: nuevo schema `UsuarioRegistrado` con `id`, `email`, `nombre`, `activo`, `debe_cambiar_password`, `cliente_id`, sin `password_hash`. Código `201`.

9. **RBAC**: endpoint en `router_publico`, sin dependencias de autenticación ni de roles.

10. **Sesión del request**: el handler depende de `get_session` e instancia `RegistroUnitOfWork(sesion)`; no se usa `get_uow` (que devuelve el UoW base).

## Risks / Trade-offs

- [Race email/documento] → mitigación: restricciones UNIQUE + captura de `IntegrityError` por etapa de flush; el perdedor responde `409`.
- [Mapeo ambiguo de IntegrityError] → se captura en el momento del flush de cada entidad, por lo que el código refleja la etapa que falló.
- [Import circular usuarios↔clientes] → `clientes.models.Cliente` se importa en `usuarios/service.py`; `clientes` no importa `usuarios` a nivel de módulo, por lo que no hay ciclo.
- [Hash previo al bloque] → la contraseña se hashea antes de validar duplicados; se acepta el costo de CPU en registros inválidos por email/documento duplicado.

## Migration Plan

Sin migración Alembic. Verificar `alembic check` limpio. Rollback: revertir código; no hay cambios de datos ni de esquema.

## Open Questions

- (ninguna)