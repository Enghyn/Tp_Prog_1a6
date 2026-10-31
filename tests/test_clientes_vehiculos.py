import pytest
from datetime import datetime, timezone
from sqlalchemy import select, text

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_usuario_prueba,
    crear_asignacion_prueba,
    token_de_sesion,
)
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo


@pytest.mark.asyncio
async def test_post_cliente_201(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC1", "telefono": "123"})
        assert r.status_code == 201
        assert r.json()["documento"] == "DOC1"


@pytest.mark.asyncio
async def test_post_cliente_documento_duplicado_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC2", "telefono": "123"})
        r = await c.post("/clientes", json={"nombre": "Otro", "documento": "DOC2", "telefono": "456"})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_cliente_200_con_vehiculos(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC3", "telefono": "123"})
        cid = r.json()["id"]
        await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "ABC123", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        r2 = await c.get(f"/clientes/{cid}")
        assert r2.status_code == 200
        assert len(r2.json()["vehiculos"]) == 1


@pytest.mark.asyncio
async def test_get_cliente_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.get("/clientes/999999")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_vehiculo_patente_duplicada_vigente_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC4", "telefono": "123"})
        cid = r.json()["id"]
        await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT1", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT1", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_patente_reusable_tras_baja(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC5", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT2", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = r2.json()["id"]
        await c.delete(f"/vehiculos/{vid}")
        r3 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT2", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        assert r3.status_code == 201


@pytest.mark.asyncio
async def test_delete_vehiculo_204(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC6", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT3", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = r2.json()["id"]
        r3 = await c.delete(f"/vehiculos/{vid}")
        assert r3.status_code == 204


@pytest.mark.asyncio
async def test_delete_vehiculo_con_orden_abierta_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/clientes", json={"nombre": "Juan", "documento": "DOC7", "telefono": "123"})
        cid = r.json()["id"]
        r2 = await c.post(f"/clientes/{cid}/vehiculos", json={"patente": "PAT4", "marca": "Ford", "modelo": "Fiesta", "anio": 2020})
        vid = r2.json()["id"]
    # insert estado orden + orden
    await contexto_auth.execute(text("INSERT INTO estado_orden (codigo, descripcion, posicion, es_final) VALUES ('PENDIENTE', 'Pendiente', 1, false) ON CONFLICT DO NOTHING"))
    await contexto_auth.flush()
    orden = OrdenTrabajo(vehiculo_id=vid, estado="PENDIENTE", falla="x", creada_en=datetime.now(timezone.utc))
    contexto_auth.add(orden)
    await contexto_auth.flush()
    async with cliente_http(token) as c:
        r3 = await c.delete(f"/vehiculos/{vid}")
        assert r3.status_code == 409


@pytest.mark.asyncio
async def test_delete_vehiculo_404(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.delete("/vehiculos/999999")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_mis_vehiculos_ok(contexto_auth):
    usuario = await crear_usuario_prueba(contexto_auth, "cliente@taller.test")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    cliente = Cliente(nombre="Juan", documento="DOC8", telefono="123", usuario_id=usuario.id)
    contexto_auth.add(cliente)
    await contexto_auth.flush()
    v = Vehiculo(cliente_id=cliente.id, patente="PAT5", marca="Ford", modelo="Fiesta", anio=2020)
    contexto_auth.add(v)
    await contexto_auth.flush()
    token = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token) as c:
        r = await c.get("/mis-vehiculos")
        assert r.status_code == 200
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_mis_vehiculos_sin_rol_403(contexto_auth):
    usuario = await crear_usuario_prueba(contexto_auth, "norole@taller.test")
    token = token_de_sesion(usuario.id, [])
    async with cliente_http(token) as c:
        r = await c.get("/mis-vehiculos")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_mis_vehiculos_sin_cliente_404(contexto_auth):
    usuario = await crear_usuario_prueba(contexto_auth, "nocliente@taller.test")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    token = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token) as c:
        r = await c.get("/mis-vehiculos")
        assert r.status_code == 404