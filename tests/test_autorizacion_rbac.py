"""
Tests de autorización RBAC (C-10): roles vigentes leídos de la base,
exigencia de roles por router, gating de contraseña pendiente y helpers
de propiedad (RN-17).

Todos los tests corren contra PostgreSQL real (regla dura #9).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, text

import main
from main import app
from app.core.seguridad import crear_token_acceso, hash_password_sync
from app.modules.usuarios.models import AsignacionRol, Usuario

BASE_URL = "http://test"


async def _crear_usuario(
    sesion,
    email: str,
    *,
    activo: bool = True,
    debe_cambiar_password: bool = False,
    password_cambiada_en: datetime | None = None,
) -> Usuario:
    usuario = Usuario(
        email=email,
        nombre="Usuario de prueba",
        password_hash=hash_password_sync("password123"),
        activo=activo,
        debe_cambiar_password=debe_cambiar_password,
        password_cambiada_en=password_cambiada_en,
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


async def _asignar_rol(
    sesion,
    usuario_id: int,
    rol: str,
    *,
    desde: datetime | None = None,
    vence_en: datetime | None = None,
    revocada_en: datetime | None = None,
) -> AsignacionRol:
    asignacion = AsignacionRol(
        usuario_id=usuario_id,
        rol=rol,
        desde=desde or datetime.now(timezone.utc),
        vence_en=vence_en,
        revocada_en=revocada_en,
    )
    sesion.add(asignacion)
    await sesion.flush()
    return asignacion


def _token_para(usuario_id: int, roles: list[str] | None = None) -> str:
    return crear_token_acceso(
        usuario_id=usuario_id,
        roles=roles or [],
        iat=datetime.now(timezone.utc),
    )


def _cliente_http(token: str | None = None) -> AsyncClient:
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    if token is not None:
        cliente.cookies.set("access_token", token)
    return cliente


def _aplanar_rutas(contenedor) -> list[APIRoute]:
    """Devuelve los `APIRoute` de un router o app, resolviendo routers incluidos."""
    rutas: list[APIRoute] = []
    for ruta in contenedor.routes:
        if isinstance(ruta, APIRoute):
            rutas.append(ruta)
        else:
            interno = getattr(ruta, "original_router", None)
            if interno is not None:
                rutas.extend(_aplanar_rutas(interno))
    return rutas


@pytest.fixture
def montar_sonda():
    """Monta un router sonda sobre la app real y lo retira al terminar."""
    agregadas = []

    def _montar(router: APIRouter) -> APIRouter:
        antes = {id(ruta) for ruta in app.router.routes}
        app.include_router(router)
        agregadas.extend(
            ruta for ruta in app.router.routes if id(ruta) not in antes
        )
        return router

    yield _montar

    for ruta in agregadas:
        if ruta in app.router.routes:
            app.router.routes.remove(ruta)


def _sonda_roles(*roles: str, ruta: str) -> APIRouter:
    from app.core.dependencies import SesionActual, require_roles

    sonda = APIRouter()

    @sonda.get(ruta)
    async def endpoint(
        sesion_actual: SesionActual = Depends(require_roles(*roles)),
    ) -> dict[str, int]:
        return {"usuario_id": sesion_actual.usuario.id}

    return sonda


@pytest.mark.asyncio
async def test_contexto_auth_conecta_postgresql(contexto_auth):
    """Task 1.4: la fixture habla con PostgreSQL real, no con SQLite."""
    resultado = await contexto_auth.execute(text("SELECT current_database()"))
    assert resultado.scalar_one()


@pytest.mark.asyncio
async def test_roles_vigentes_sin_vencimiento(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "vigente-null@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "ADMIN")

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == ["ADMIN"]


@pytest.mark.asyncio
async def test_roles_vigentes_con_vencimiento_futuro(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "vigente-futuro@taller.test")
    await _asignar_rol(
        contexto_auth,
        usuario.id,
        "MECANICO",
        vence_en=datetime.now(timezone.utc) + timedelta(days=1),
    )

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == ["MECANICO"]


@pytest.mark.asyncio
async def test_roles_vigentes_con_vencimiento_pasado_no_autoriza(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "vencido@taller.test")
    await _asignar_rol(
        contexto_auth,
        usuario.id,
        "MECANICO",
        vence_en=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == []


@pytest.mark.asyncio
async def test_roles_vigentes_revocado_no_autoriza(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "revocado@taller.test")
    await _asignar_rol(
        contexto_auth,
        usuario.id,
        "RECEPCION",
        revocada_en=datetime.now(timezone.utc),
    )

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == []


@pytest.mark.asyncio
async def test_roles_vigentes_usuario_sin_asignaciones(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "sin-roles@taller.test")

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == []


@pytest.mark.asyncio
async def test_roles_vigentes_dos_roles_ordenados(contexto_auth):
    from app.core.dependencies import get_roles_vigentes

    usuario = await _crear_usuario(contexto_auth, "dos-roles@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "RECEPCION")
    await _asignar_rol(contexto_auth, usuario.id, "ADMIN")

    roles = await get_roles_vigentes(contexto_auth, usuario.id)

    assert roles == ["ADMIN", "RECEPCION"]


@pytest.mark.asyncio
async def test_roles_vigentes_vencimiento_exacto_no_autoriza(contexto_auth, monkeypatch):
    """Task 2.4: `vence_en == ahora` no autoriza (comparación estricta `>`)."""
    from app.modules.usuarios import repository

    instante = datetime(2026, 10, 31, 12, 0, 0, 0, tzinfo=timezone.utc)

    class RelojFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante

    monkeypatch.setattr(repository, "datetime", RelojFijo)

    usuario = await _crear_usuario(contexto_auth, "vence-exacto@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "ADMIN", vence_en=instante)

    roles = await repository.obtener_roles_vigentes_por_usuario(contexto_auth, usuario.id)

    assert roles == []


@pytest.mark.asyncio
async def test_roles_vigentes_vencimiento_un_microsegundo_futuro_autoriza(
    contexto_auth, monkeypatch
):
    """Task 2.4: `vence_en = ahora + 1µs` sí autoriza."""
    from app.modules.usuarios import repository

    instante = datetime(2026, 10, 31, 12, 0, 0, 0, tzinfo=timezone.utc)

    class RelojFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante

    monkeypatch.setattr(repository, "datetime", RelojFijo)

    usuario = await _crear_usuario(contexto_auth, "vence-micro@taller.test")
    await _asignar_rol(
        contexto_auth,
        usuario.id,
        "ADMIN",
        vence_en=instante + timedelta(microseconds=1),
    )

    roles = await repository.obtener_roles_vigentes_por_usuario(contexto_auth, usuario.id)

    assert roles == ["ADMIN"]

# ==============================================================================
# Section 3: require_roles
# ==============================================================================


@pytest.mark.asyncio
async def test_require_roles_sin_cookie_devuelve_401(montar_sonda):
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-sin-cookie"))

    async with _cliente_http() as cliente:
        respuesta = await cliente.get("/sonda/roles-sin-cookie")

    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "detail": "Credenciales inválidas",
        "codigo": "CREDENCIALES_INVALIDAS",
    }


@pytest.mark.asyncio
async def test_require_roles_token_expirado_devuelve_401(montar_sonda, contexto_auth):
    usuario = await _crear_usuario(contexto_auth, "roles-expirado@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "ADMIN")
    token = crear_token_acceso(
        usuario_id=usuario.id,
        roles=["ADMIN"],
        iat=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-expirado"))

    async with _cliente_http(token) as cliente:
        respuesta = await cliente.get("/sonda/roles-expirado")

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "CREDENCIALES_INVALIDAS"


@pytest.mark.asyncio
async def test_require_roles_sin_rol_devuelve_403(montar_sonda, contexto_auth):
    usuario = await _crear_usuario(contexto_auth, "roles-sin-rol@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "RECEPCION")
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-sin-rol"))

    async with _cliente_http(_token_para(usuario.id, ["RECEPCION"])) as cliente:
        respuesta = await cliente.get("/sonda/roles-sin-rol")

    assert respuesta.status_code == 403
    assert respuesta.json() == {
        "detail": "Permisos insuficientes",
        "codigo": "PERMISOS_INSUFICIENTES",
    }


@pytest.mark.asyncio
async def test_require_roles_con_rol_vigente_devuelve_200(montar_sonda, contexto_auth):
    usuario = await _crear_usuario(contexto_auth, "roles-con-rol@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "ADMIN")
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-con-rol"))

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/sonda/roles-con-rol")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": usuario.id}


@pytest.mark.asyncio
async def test_require_roles_acepta_cualquiera_de_los_roles(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(contexto_auth, "roles-alterno@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "RECEPCION")
    montar_sonda(
        _sonda_roles("ADMIN", "RECEPCION", ruta="/sonda/roles-alterno")
    )

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/sonda/roles-alterno")

    assert respuesta.status_code == 200


@pytest.mark.asyncio
async def test_require_roles_revocado_en_caliente_pierde_acceso(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(contexto_auth, "roles-revocado-caliente@taller.test")
    asignacion = await _asignar_rol(contexto_auth, usuario.id, "RECEPCION")
    montar_sonda(_sonda_roles("RECEPCION", ruta="/sonda/roles-revocado"))

    token = _token_para(usuario.id, ["RECEPCION"])
    async with _cliente_http(token) as cliente:
        primera = await cliente.get("/sonda/roles-revocado")
        assert primera.status_code == 200

        asignacion.revocada_en = datetime.now(timezone.utc)
        await contexto_auth.flush()

        segunda = await cliente.get("/sonda/roles-revocado")

    assert segunda.status_code == 403
    assert segunda.json()["codigo"] == "PERMISOS_INSUFICIENTES"


@pytest.mark.asyncio
async def test_require_roles_concedido_en_caliente_habilita_sin_reemitir_token(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(contexto_auth, "roles-concedido-caliente@taller.test")
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-concedido"))

    # Token emitido sin ADMIN
    token = _token_para(usuario.id, [])
    async with _cliente_http(token) as cliente:
        await _asignar_rol(contexto_auth, usuario.id, "ADMIN")
        respuesta = await cliente.get("/sonda/roles-concedido")

    assert respuesta.status_code == 200


@pytest.mark.asyncio
async def test_require_roles_claim_del_token_no_autoriza(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(contexto_auth, "roles-claim@taller.test")
    await _asignar_rol(contexto_auth, usuario.id, "RECEPCION")
    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/roles-claim"))

    # El token declara ADMIN, pero la base sólo tiene RECEPCION vigente.
    token = _token_para(usuario.id, ["ADMIN"])
    async with _cliente_http(token) as cliente:
        respuesta = await cliente.get("/sonda/roles-claim")

    assert respuesta.status_code == 403


def test_require_roles_rol_desconocido_falla_al_construir():
    from app.core.dependencies import require_roles

    with pytest.raises(ValueError):
        require_roles("ADMN")


def test_require_roles_documenta_uso_de_router_y_endpoint():
    from app.core.dependencies import require_roles

    docstring = require_roles.__doc__ or ""
    assert "APIRouter" in docstring
    assert "Depends" in docstring


# ==============================================================================
# Section 4: grupos de rutas y gating de contraseña pendiente (RN-06)
# ==============================================================================


def _sonda_password(ruta: str) -> APIRouter:
    from app.core.dependencies import requiere_password_actualizada

    sonda = APIRouter(dependencies=[Depends(requiere_password_actualizada)])

    @sonda.get(ruta)
    async def endpoint() -> dict[str, bool]:
        return {"ok": True}

    return sonda


@pytest.mark.asyncio
async def test_password_pendiente_bloquea_ruta_de_dominio(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(
        contexto_auth, "password-pendiente@taller.test", debe_cambiar_password=True
    )
    montar_sonda(_sonda_password("/sonda/password-pendiente"))

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/sonda/password-pendiente")

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"


@pytest.mark.asyncio
async def test_password_pendiente_permite_auth_yo(contexto_auth):
    usuario = await _crear_usuario(
        contexto_auth, "password-yo@taller.test", debe_cambiar_password=True
    )
    await _asignar_rol(contexto_auth, usuario.id, "CLIENTE")

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/auth/yo")

    assert respuesta.status_code == 200
    assert respuesta.json()["usuario"]["debe_cambiar_password"] is True


@pytest.mark.asyncio
async def test_password_pendiente_no_bloquea_health_live(contexto_auth):
    usuario = await _crear_usuario(
        contexto_auth, "password-health@taller.test", debe_cambiar_password=True
    )

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/health/live")

    assert respuesta.status_code == 200


@pytest.mark.asyncio
async def test_password_actualizada_permite_ruta_de_dominio(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(
        contexto_auth, "password-ok@taller.test", debe_cambiar_password=False
    )
    montar_sonda(_sonda_password("/sonda/password-ok"))

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/sonda/password-ok")

    assert respuesta.status_code == 200


@pytest.mark.asyncio
async def test_password_activada_despues_del_token_bloquea(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(
        contexto_auth, "password-tardia@taller.test", debe_cambiar_password=False
    )
    montar_sonda(_sonda_password("/sonda/password-tardia"))
    token = _token_para(usuario.id)

    async with _cliente_http(token) as cliente:
        primera = await cliente.get("/sonda/password-tardia")
        assert primera.status_code == 200

        usuario.debe_cambiar_password = True
        await contexto_auth.flush()

        segunda = await cliente.get("/sonda/password-tardia")

    assert segunda.status_code == 403
    assert segunda.json()["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"


@pytest.mark.asyncio
async def test_password_gating_sin_cookie_devuelve_401(montar_sonda):
    montar_sonda(_sonda_password("/sonda/password-sin-cookie"))

    async with _cliente_http() as cliente:
        respuesta = await cliente.get("/sonda/password-sin-cookie")

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "CREDENCIALES_INVALIDAS"


@pytest.mark.asyncio
async def test_password_gating_no_revela_datos_del_usuario(
    montar_sonda, contexto_auth
):
    usuario = await _crear_usuario(
        contexto_auth, "password-cuerpo@taller.test", debe_cambiar_password=True
    )
    montar_sonda(_sonda_password("/sonda/password-cuerpo"))

    async with _cliente_http(_token_para(usuario.id)) as cliente:
        respuesta = await cliente.get("/sonda/password-cuerpo")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 403
    assert set(cuerpo.keys()) == {"detail", "codigo"}
    assert cuerpo["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"
    assert "roles" not in cuerpo


def test_cableado_grupos_publico_y_protegido():
    """Task 4.5: introspección del montaje real en `main`."""
    from app.core.dependencies import requiere_password_actualizada

    publico = {ruta.path for ruta in _aplanar_rutas(main.router_publico)}
    protegido = {ruta.path for ruta in _aplanar_rutas(main.router_protegido)}

    assert {"/health/live", "/health/ready"} <= publico
    assert {"/auth/login", "/auth/logout"} <= publico
    assert "/auth/yo" in protegido
    assert "/auth/yo" not in publico

    dependencias = [
        dependencia.dependency
        for dependencia in main.router_protegido.dependencies
    ]
    assert requiere_password_actualizada in dependencias


def test_cableado_sin_rutas_de_dominio_fuera_de_los_grupos():
    """Task 4.8: una app recién creada sólo monta los dos grupos.

    Se construye una app limpia para no depender de rutas que otros módulos
    de test agregan a la instancia global `app`.
    """
    app_limpia = main.create_app()
    rutas_app = {ruta.path for ruta in _aplanar_rutas(app_limpia)}
    rutas_grupos = {
        ruta.path
        for grupo in (main.router_publico, main.router_protegido)
        for ruta in _aplanar_rutas(grupo)
    }

    assert rutas_app == rutas_grupos


@pytest.mark.asyncio
async def test_logout_sin_cookie_sigue_siendo_200_idempotente():
    """Task 4.7: contrato heredado de C-09, logout público."""
    async with _cliente_http() as cliente:
        respuesta = await cliente.post("/auth/logout")

    assert respuesta.status_code == 200
    cookie = respuesta.headers.get("set-cookie", "").lower()
    assert "access_token=" in cookie
    assert "max-age=0" in cookie


# ==============================================================================
# Section 5: helpers de propiedad (RN-17)
# ==============================================================================


async def _crear_cliente(sesion, usuario: Usuario, documento: str):
    from app.modules.clientes.models import Cliente

    cliente = Cliente(
        usuario_id=usuario.id,
        nombre="Cliente de prueba",
        documento=documento,
        telefono="555-0000",
    )
    sesion.add(cliente)
    await sesion.flush()
    return cliente


async def _crear_vehiculo(
    sesion,
    cliente_id: int,
    patente: str,
    *,
    borrado_en: datetime | None = None,
):
    from app.modules.clientes.models import Vehiculo

    vehiculo = Vehiculo(
        cliente_id=cliente_id,
        patente=patente,
        marca="Marca",
        modelo="Modelo",
        anio=2020,
        borrado_en=borrado_en,
    )
    sesion.add(vehiculo)
    await sesion.flush()
    return vehiculo


async def _crear_orden(sesion, vehiculo_id: int, *, mecanico_id: int | None = None):
    from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo

    estado = await sesion.get(EstadoOrden, "RBAC_TEST")
    if estado is None:
        estado = EstadoOrden(
            codigo="RBAC_TEST",
            descripcion="Estado de prueba RBAC",
            posicion=9001,
            es_final=False,
        )
        sesion.add(estado)
        await sesion.flush()

    orden = OrdenTrabajo(
        vehiculo_id=vehiculo_id,
        mecanico_id=mecanico_id,
        estado=estado.codigo,
        falla="Falla de prueba",
        creada_en=datetime.now(timezone.utc),
        total=Decimal("0"),
    )
    sesion.add(orden)
    await sesion.flush()
    return orden


async def _escenario_dos_clientes(sesion):
    duenio = await _crear_usuario(sesion, "duenio@taller.test")
    otro = await _crear_usuario(sesion, "otro-cliente@taller.test")
    sin_ficha = await _crear_usuario(sesion, "sin-ficha@taller.test")

    cliente_duenio = await _crear_cliente(sesion, duenio, "DOC-DUENIO")
    cliente_otro = await _crear_cliente(sesion, otro, "DOC-OTRO")

    vehiculo_propio = await _crear_vehiculo(sesion, cliente_duenio.id, "AAA111")
    vehiculo_ajeno = await _crear_vehiculo(sesion, cliente_otro.id, "BBB222")

    return duenio, otro, sin_ficha, vehiculo_propio, vehiculo_ajeno


@pytest.mark.asyncio
async def test_duenio_de_vehiculo_propio(contexto_auth):
    from app.core.dependencies import es_duenio_de_vehiculo

    duenio, _, _, vehiculo_propio, _ = await _escenario_dos_clientes(contexto_auth)

    assert await es_duenio_de_vehiculo(contexto_auth, duenio.id, vehiculo_propio.id)


@pytest.mark.asyncio
async def test_duenio_de_vehiculo_ajeno(contexto_auth):
    from app.core.dependencies import es_duenio_de_vehiculo

    duenio, _, _, _, vehiculo_ajeno = await _escenario_dos_clientes(contexto_auth)

    assert not await es_duenio_de_vehiculo(
        contexto_auth, duenio.id, vehiculo_ajeno.id
    )


@pytest.mark.asyncio
async def test_duenio_de_vehiculo_inexistente(contexto_auth):
    from app.core.dependencies import es_duenio_de_vehiculo

    duenio, _, _, _, _ = await _escenario_dos_clientes(contexto_auth)

    assert not await es_duenio_de_vehiculo(contexto_auth, duenio.id, 999999)


@pytest.mark.asyncio
async def test_duenio_de_vehiculo_usuario_sin_ficha(contexto_auth):
    from app.core.dependencies import es_duenio_de_vehiculo

    _, _, sin_ficha, vehiculo_propio, _ = await _escenario_dos_clientes(contexto_auth)

    assert not await es_duenio_de_vehiculo(
        contexto_auth, sin_ficha.id, vehiculo_propio.id
    )


@pytest.mark.asyncio
async def test_duenio_de_orden_propia(contexto_auth):
    from app.core.dependencies import es_duenio_de_orden

    duenio, _, _, vehiculo_propio, _ = await _escenario_dos_clientes(contexto_auth)
    orden = await _crear_orden(contexto_auth, vehiculo_propio.id)

    assert await es_duenio_de_orden(contexto_auth, duenio.id, orden.id)


@pytest.mark.asyncio
async def test_duenio_de_orden_ajena(contexto_auth):
    from app.core.dependencies import es_duenio_de_orden

    duenio, _, _, _, vehiculo_ajeno = await _escenario_dos_clientes(contexto_auth)
    orden = await _crear_orden(contexto_auth, vehiculo_ajeno.id)

    assert not await es_duenio_de_orden(contexto_auth, duenio.id, orden.id)


@pytest.mark.asyncio
async def test_duenio_de_orden_inexistente(contexto_auth):
    from app.core.dependencies import es_duenio_de_orden

    duenio, _, _, _, _ = await _escenario_dos_clientes(contexto_auth)

    assert not await es_duenio_de_orden(contexto_auth, duenio.id, 999999)


@pytest.mark.asyncio
async def test_mecanico_asignado_no_es_duenio_de_orden(contexto_auth):
    """D6: `mecanico_id` no otorga propiedad; RN-17 es regla CLIENTE."""
    from app.core.dependencies import es_duenio_de_orden

    _, otro, mecanico, _, vehiculo_ajeno = await _escenario_dos_clientes(contexto_auth)
    orden = await _crear_orden(
        contexto_auth, vehiculo_ajeno.id, mecanico_id=mecanico.id
    )

    # El vehículo sí es de `otro`, pero el mecánico asignado no es el dueño.
    assert await es_duenio_de_orden(contexto_auth, otro.id, orden.id)
    assert not await es_duenio_de_orden(contexto_auth, mecanico.id, orden.id)


@pytest.mark.asyncio
async def test_propiedad_ignora_borrado_en(contexto_auth):
    """D6: un vehículo de baja lógica sigue siendo del cliente en el historial."""
    from app.core.dependencies import es_duenio_de_orden, es_duenio_de_vehiculo

    duenio = await _crear_usuario(contexto_auth, "duenio-baja@taller.test")
    cliente = await _crear_cliente(contexto_auth, duenio, "DOC-BAJA")
    vehiculo = await _crear_vehiculo(
        contexto_auth,
        cliente.id,
        "CCC333",
        borrado_en=datetime.now(timezone.utc),
    )
    orden = await _crear_orden(contexto_auth, vehiculo.id)

    assert await es_duenio_de_vehiculo(contexto_auth, duenio.id, vehiculo.id)
    assert await es_duenio_de_orden(contexto_auth, duenio.id, orden.id)


# ==============================================================================
# Section 6: integración de cierre
# ==============================================================================


@pytest.mark.asyncio
async def test_contrato_observable_de_punta_a_punta(montar_sonda, contexto_auth):
    """Task 6.3: los cuatro comportamientos observables en una sola corrida."""
    usuario_revocado = await _crear_usuario(
        contexto_auth, "e2e-revocado@taller.test"
    )
    await _asignar_rol(
        contexto_auth,
        usuario_revocado.id,
        "ADMIN",
        revocada_en=datetime.now(timezone.utc),
    )
    usuario_password = await _crear_usuario(
        contexto_auth, "e2e-password@taller.test", debe_cambiar_password=True
    )

    montar_sonda(_sonda_roles("ADMIN", ruta="/sonda/e2e-rol"))
    montar_sonda(_sonda_password("/sonda/e2e-password"))

    async with _cliente_http() as cliente:
        assert (await cliente.get("/health/live")).status_code == 200
        assert (await cliente.get("/auth/yo")).status_code == 401

    async with _cliente_http(_token_para(usuario_revocado.id, ["ADMIN"])) as cliente:
        respuesta_rol = await cliente.get("/sonda/e2e-rol")
    assert respuesta_rol.status_code == 403
    assert respuesta_rol.json()["codigo"] == "PERMISOS_INSUFICIENTES"

    async with _cliente_http(_token_para(usuario_password.id)) as cliente:
        respuesta_dominio = await cliente.get("/sonda/e2e-password")
        respuesta_yo = await cliente.get("/auth/yo")
    assert respuesta_dominio.status_code == 403
    assert respuesta_dominio.json()["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"
    assert respuesta_yo.status_code == 200


@pytest.mark.asyncio
async def test_helpers_de_propiedad_emiten_una_sola_sentencia(contexto_auth):
    """Task 5.6: una sola sentencia SQL, sin lazy loading ni N+1."""
    from app.core.dependencies import es_duenio_de_orden, es_duenio_de_vehiculo

    duenio, _, _, vehiculo_propio, _ = await _escenario_dos_clientes(contexto_auth)
    orden = await _crear_orden(contexto_auth, vehiculo_propio.id)
    await contexto_auth.flush()

    sentencias: list[str] = []

    def _registrar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            sentencias.append(statement)

    conexion = contexto_auth.bind
    objetivo = getattr(conexion, "sync_engine", None) or conexion.sync_connection
    event.listen(objetivo, "before_cursor_execute", _registrar)
    try:
        assert await es_duenio_de_vehiculo(
            contexto_auth, duenio.id, vehiculo_propio.id
        )
        assert len(sentencias) == 1
        assert "EXISTS" in sentencias[0].upper()

        sentencias.clear()
        assert await es_duenio_de_orden(contexto_auth, duenio.id, orden.id)
        assert len(sentencias) == 1
        assert "EXISTS" in sentencias[0].upper()
    finally:
        event.remove(objetivo, "before_cursor_execute", _registrar)
