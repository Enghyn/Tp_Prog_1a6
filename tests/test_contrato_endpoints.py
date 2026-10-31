import pytest
from datetime import datetime, timezone

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_health_live_200():
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health/live")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_contrato_health_ready_200(contexto_auth):
    async with cliente_http() as c:
        r = await c.get("/health/ready")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_auth_registro_201_y_409(contexto_auth):
    async with cliente_http() as c:
        r = await c.post("/auth/registro", json={
            "email": "ctr.reg@example.com", "nombre": "Reg",
            "password": "Password123", "documento": "DOC-CTR-REG",
            "telefono": "123",
        })
        assert r.status_code == 201
        r2 = await c.post("/auth/registro", json={
            "email": "ctr.reg@example.com", "nombre": "Reg2",
            "password": "Password123", "documento": "DOC-CTR-REG2",
            "telefono": "123",
        })
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contrato_auth_login_200_y_401(contexto_auth):
    await crear_usuario_prueba(contexto_auth, "ctr.login@example.com", password="Password123")
    await contexto_auth.flush()
    async with cliente_http() as c:
        r = await c.post("/auth/login", json={"email": "ctr.login@example.com", "password": "Password123"})
        assert r.status_code == 200
        r2 = await c.post("/auth/login", json={"email": "ctr.login@example.com", "password": "Mala1234"})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_contrato_auth_logout_200(contexto_auth):
    async with cliente_http() as c:
        r = await c.post("/auth/logout")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_contrato_auth_yo_200_y_401(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/auth/yo")
        assert r.status_code == 200
    async with cliente_http() as c:
        r2 = await c.get("/auth/yo")
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_contrato_auth_cambiar_password_200_y_422(contexto_auth):
    usuario = await crear_usuario_prueba(contexto_auth, "ctr.cp@example.com", password="Password123")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    token = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token) as c:
        r2 = await c.post("/auth/cambiar-password", json={
            "password_actual": "Password123", "password_nueva": "corta",
        })
        assert r2.status_code == 422
        r = await c.post("/auth/cambiar-password", json={
            "password_actual": "Password123", "password_nueva": "NuevaPass1",
        })
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Usuarios (admin)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_usuarios_alta_201_y_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/usuarios", json={"email": "ctr.pers@example.com", "nombre": "P", "password": "Password123"})
        assert r.status_code == 201
        r2 = await c.post("/usuarios", json={"email": "ctr.pers@example.com", "nombre": "P2", "password": "Password123"})
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contrato_usuarios_roles_get_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get(f"/usuarios/{admin.id}/roles")
        assert r.status_code == 200
        r2 = await c.get("/usuarios/999999/roles")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_usuarios_roles_post_201_y_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario = await crear_usuario_prueba(contexto_auth, "ctr.rol@example.com")
    await contexto_auth.flush()
    async with cliente_http(token) as c:
        r = await c.post(f"/usuarios/{usuario.id}/roles", json={"rol": "MECANICO"})
        assert r.status_code == 201
        r2 = await c.post(f"/usuarios/{usuario.id}/roles", json={"rol": "MECANICO"})
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contrato_usuarios_roles_delete_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario = await crear_usuario_prueba(contexto_auth, "ctr.rev@example.com")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "MECANICO")
    await contexto_auth.flush()
    async with cliente_http(token) as c:
        r = await c.delete(f"/usuarios/{usuario.id}/roles/MECANICO")
        assert r.status_code == 200
        r2 = await c.delete(f"/usuarios/{usuario.id}/roles/MECANICO")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_eventos_200_y_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/eventos?page=1&size=10")
        assert r.status_code == 200
        r2 = await c.get("/eventos?page=1&size=0")
        assert r2.status_code == 422


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_clientes_post_201_y_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-C1", "telefono": "123"})
        assert r.status_code == 201
        r2 = await c.post("/clientes", json={"nombre": "Otro", "documento": "DOC-CTR-C1", "telefono": "456"})
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contrato_clientes_get_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-C2", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.get(f"/clientes/{cid}")
        assert r2.status_code == 200
        r3 = await c.get("/clientes/999999")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_clientes_vehiculo_post_201_y_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-C3", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-1", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        assert r2.status_code == 201
        r3 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-1", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        assert r3.status_code == 409


@pytest.mark.asyncio
async def test_contrato_vehiculos_delete_204_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-C4", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-2", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = r2.json()["id"]
        r3 = await c.delete(f"/vehiculos/{vid}")
        assert r3.status_code == 204
        r4 = await c.delete("/vehiculos/999999")
        assert r4.status_code == 404


@pytest.mark.asyncio
async def test_contrato_mis_vehiculos_200(contexto_auth):
    from app.modules.clientes.models import Cliente
    usuario = await crear_usuario_prueba(contexto_auth, "ctr.mv@example.com")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    cliente = Cliente(usuario_id=usuario.id, nombre="MV", documento="DOC-MV", telefono="1")
    contexto_auth.add(cliente)
    await contexto_auth.flush()
    token = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token) as c:
        r = await c.get("/mis-vehiculos")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Repuestos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_repuestos_list_200_y_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/repuestos?page=1&size=10")
        assert r.status_code == 200
        r2 = await c.get("/repuestos?page=1&size=0")
        assert r2.status_code == 422


@pytest.mark.asyncio
async def test_contrato_repuestos_get_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-1", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.get(f"/repuestos/{rid}")
        assert r2.status_code == 200
        r3 = await c.get("/repuestos/999999")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_repuestos_post_201_y_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-2", "descripcion": "d", "precio": "10.0", "stock": 1})
        assert r.status_code == 201
        r2 = await c.post("/repuestos", json={"codigo": "REP-CTR-2", "descripcion": "d2", "precio": "10.0", "stock": 1})
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contrato_repuestos_patch_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-3", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.patch(f"/repuestos/{rid}", json={"precio": "12.0"})
        assert r2.status_code == 200
        r3 = await c.patch("/repuestos/999999", json={"precio": "12.0"})
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_repuestos_delete_204_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-4", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.delete(f"/repuestos/{rid}")
        assert r2.status_code == 204
        r3 = await c.delete("/repuestos/999999")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_repuestos_reponer_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-5", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.post(f"/repuestos/{rid}/reponer", json={"cantidad": 2})
        assert r2.status_code == 200
        r3 = await c.post("/repuestos/999999/reponer", json={"cantidad": 2})
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_repuestos_movimientos_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-6", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.get(f"/repuestos/{rid}/movimientos")
        assert r2.status_code == 200
        r3 = await c.get("/repuestos/999999/movimientos")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_contrato_repuestos_precios_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "REP-CTR-7", "descripcion": "d", "precio": "10.0", "stock": 1})
        rid = r.json()["id"]
        r2 = await c.get(f"/repuestos/{rid}/precios")
        assert r2.status_code == 200
        r3 = await c.get("/repuestos/999999/precios")
        assert r3.status_code == 404


# ---------------------------------------------------------------------------
# Ordenes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contrato_ordenes_post_201_y_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    # crear cliente + vehiculo + repuesto
    async with cliente_http(token) as c:
        cr = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-O1", "telefono": "123"})
        cid = cr.json()["id"]
        vr = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-O1", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = vr.json()["id"]
        rr = await c.post("/repuestos", json={"codigo": "REP-CTR-O1", "descripcion": "d", "precio": "10.0", "stock": 5})
        rid = rr.json()["id"]
        r = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "ruido", "items": [{"repuesto_id": rid, "cantidad": 1}]})
        assert r.status_code == 201
        r2 = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "x", "items": [{"repuesto_id": rid, "cantidad": 1}, {"repuesto_id": rid, "cantidad": 2}]})
        assert r2.status_code == 422


@pytest.mark.asyncio
async def test_contrato_ordenes_list_200_y_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/ordenes?page=1&size=10")
        assert r.status_code == 200
        r2 = await c.get("/ordenes?page=1&size=10&estado=NOPE")
        assert r2.status_code == 422


@pytest.mark.asyncio
async def test_contrato_ordenes_get_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        cr = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-O2", "telefono": "123"})
        cid = cr.json()["id"]
        vr = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-O2", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = vr.json()["id"]
        rr = await c.post("/repuestos", json={"codigo": "REP-CTR-O2", "descripcion": "d", "precio": "10.0", "stock": 5})
        rid = rr.json()["id"]
        orr = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "ruido", "items": [{"repuesto_id": rid, "cantidad": 1}]})
        oid = orr.json()["id"]
        r = await c.get(f"/ordenes/{oid}")
        assert r.status_code == 200
        r2 = await c.get("/ordenes/999999")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_ordenes_iniciar_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    # mecanico token
    mec = await crear_usuario_prueba(contexto_auth, "ctr.mec@example.com")
    await crear_asignacion_prueba(contexto_auth, mec.id, "MECANICO")
    mec_token = token_de_sesion(mec.id, ["MECANICO"])
    async with cliente_http(token) as c:
        cr = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-O3", "telefono": "123"})
        cid = cr.json()["id"]
        vr = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-O3", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = vr.json()["id"]
        rr = await c.post("/repuestos", json={"codigo": "REP-CTR-O3", "descripcion": "d", "precio": "10.0", "stock": 5})
        rid = rr.json()["id"]
        orr = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "ruido", "items": [{"repuesto_id": rid, "cantidad": 1}]})
        oid = orr.json()["id"]
    async with cliente_http(mec_token) as c:
        r = await c.post(f"/ordenes/{oid}/iniciar")
        assert r.status_code == 200
        r2 = await c.post("/ordenes/999999/iniciar")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_ordenes_terminar_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    mec = await crear_usuario_prueba(contexto_auth, "ctr.mec2@example.com")
    await crear_asignacion_prueba(contexto_auth, mec.id, "MECANICO")
    mec_token = token_de_sesion(mec.id, ["MECANICO"])
    async with cliente_http(token) as c:
        cr = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-O4", "telefono": "123"})
        cid = cr.json()["id"]
        vr = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-O4", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = vr.json()["id"]
        rr = await c.post("/repuestos", json={"codigo": "REP-CTR-O4", "descripcion": "d", "precio": "10.0", "stock": 5})
        rid = rr.json()["id"]
        orr = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "ruido", "items": [{"repuesto_id": rid, "cantidad": 1}]})
        oid = orr.json()["id"]
    async with cliente_http(mec_token) as c:
        await c.post(f"/ordenes/{oid}/iniciar")
        r = await c.post(f"/ordenes/{oid}/terminar")
        assert r.status_code == 200
        r2 = await c.post("/ordenes/999999/terminar")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_ordenes_cancelar_200_y_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        cr = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC-CTR-O5", "telefono": "123"})
        cid = cr.json()["id"]
        vr = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT-CTR-O5", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = vr.json()["id"]
        rr = await c.post("/repuestos", json={"codigo": "REP-CTR-O5", "descripcion": "d", "precio": "10.0", "stock": 5})
        rid = rr.json()["id"]
        orr = await c.post("/ordenes", json={"vehiculo_id": vid, "falla": "ruido", "items": [{"repuesto_id": rid, "cantidad": 1}]})
        oid = orr.json()["id"]
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 200
        r2 = await c.post("/ordenes/999999/cancelar")
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_contrato_estados_orden_200(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/estados-orden")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_contrato_mis_ordenes_200_y_422(contexto_auth):
    from app.modules.clientes.models import Cliente
    usuario = await crear_usuario_prueba(contexto_auth, "ctr.mo@example.com")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    cliente = Cliente(usuario_id=usuario.id, nombre="MO", documento="DOC-MO", telefono="1")
    contexto_auth.add(cliente)
    await contexto_auth.flush()
    token = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token) as c:
        r = await c.get("/mis-ordenes?page=1&size=10")
        assert r.status_code == 200
        r2 = await c.get("/mis-ordenes?page=1&size=0")
        assert r2.status_code == 422
