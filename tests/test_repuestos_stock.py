import pytest

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)


async def _mecanico_token(sesion):
    u = await crear_usuario_prueba(sesion, f"mec_{id(sesion)}@taller.test")
    await crear_asignacion_prueba(sesion, u.id, "MECANICO")
    return token_de_sesion(u.id, ["MECANICO"])


@pytest.mark.asyncio
async def test_listar_repuestos_paginado(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        for i in range(3):
            await c.post("/repuestos", json={
                "codigo": f"R{i}", "descripcion": f"Repuesto numero {i}", "precio": "10.50", "stock": 1
            })
        r = await c.get("/repuestos", params={"page": 1, "size": 2})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_busqueda_ilike_descripcion(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        await c.post("/repuestos", json={"codigo": "A1", "descripcion": "Filtro de aceite", "precio": "5.00", "stock": 0})
        await c.post("/repuestos", json={"codigo": "A2", "descripcion": "Pastilla de freno", "precio": "8.00", "stock": 0})
        r = await c.get("/repuestos", params={"q": "aceite"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["descripcion"] == "Filtro de aceite"


@pytest.mark.asyncio
async def test_get_repuesto_200_y_404_eliminado(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "B1", "descripcion": "Bujia", "precio": "2.00", "stock": 0})
        rid = r.json()["id"]
        r2 = await c.get(f"/repuestos/{rid}")
        assert r2.status_code == 200
        await c.delete(f"/repuestos/{rid}")
        r3 = await c.get(f"/repuestos/{rid}")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_post_repuesto_201_stock_inicial_y_movimiento_alta(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "C1", "descripcion": "Cable", "precio": "3.00", "stock": 5})
        assert r.status_code == 201
        rid = r.json()["id"]
        assert r.json()["stock"] == 5
        # movimientos
        rm = await c.get(f"/repuestos/{rid}/movimientos")
        assert rm.status_code == 200
        movs = rm.json()
        assert len(movs) == 1
        assert movs[0]["motivo"] == "ALTA"
        assert movs[0]["cantidad"] == 5


@pytest.mark.asyncio
async def test_post_repuesto_stock_cero_sin_movimiento(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "C2", "descripcion": "Sin stock", "precio": "3.00", "stock": 0})
        assert r.status_code == 201
        rid = r.json()["id"]
        rm = await c.get(f"/repuestos/{rid}/movimientos")
        assert rm.status_code == 200
        assert rm.json() == []


@pytest.mark.asyncio
async def test_patch_descripcion_y_precio_genera_historial(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "D1", "descripcion": "Original", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        rp = await c.patch(f"/repuestos/{rid}", json={"descripcion": "Nueva", "precio": "12.00"})
        assert rp.status_code == 200
        assert rp.json()["descripcion"] == "Nueva"
        assert rp.json()["precio"] == "12.00"
        rh = await c.get(f"/repuestos/{rid}/precios")
        assert rh.status_code == 200
        hist = rh.json()
        assert len(hist) == 1
        assert hist[0]["precio_anterior"] == "10.00"
        assert hist[0]["precio_nuevo"] == "12.00"


@pytest.mark.asyncio
async def test_patch_sin_cambio_precio_no_genera_historial(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "D2", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        # solo descripcion
        rp = await c.patch(f"/repuestos/{rid}", json={"descripcion": "Desc2"})
        assert rp.status_code == 200
        rh = await c.get(f"/repuestos/{rid}/precios")
        assert rh.json() == []
        # mismo precio (no cambio)
        rp2 = await c.patch(f"/repuestos/{rid}", json={"precio": "10.00"})
        assert rp2.status_code == 200
        rh2 = await c.get(f"/repuestos/{rid}/precios")
        assert rh2.json() == []


@pytest.mark.asyncio
async def test_patch_precio_menor_rechazado_409(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "D3", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        rp = await c.patch(f"/repuestos/{rid}", json={"precio": "9.00"})
        assert rp.status_code == 409


@pytest.mark.asyncio
async def test_patch_precio_igual_sin_cambio_200(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "D4", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        rp = await c.patch(f"/repuestos/{rid}", json={"precio": "10.00"})
        assert rp.status_code == 200


@pytest.mark.asyncio
async def test_patch_stock_no_editable_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "E1", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        rp = await c.patch(f"/repuestos/{rid}", json={"stock": 5})
        assert rp.status_code == 422


@pytest.mark.asyncio
async def test_delete_repuesto_204(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "F1", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
        rd = await c.delete(f"/repuestos/{rid}")
        assert rd.status_code == 204


@pytest.mark.asyncio
async def test_reponer_genera_movimiento(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "G1", "descripcion": "Desc", "precio": "10.00", "stock": 2})
        rid = r.json()["id"]
        rr = await c.post(f"/repuestos/{rid}/reponer", json={"cantidad": 3})
        assert rr.status_code == 200
        assert rr.json()["stock"] == 5
        rm = await c.get(f"/repuestos/{rid}/movimientos")
        # movimientos: ALTA + REPOSICION
        motivos = [m["motivo"] for m in rm.json()]
        assert "REPOSICION" in motivos


@pytest.mark.asyncio
async def test_solo_admin_muta_403(contexto_auth):
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    mecanico_token = await _mecanico_token(contexto_auth)
    # create repuesto as admin
    async with cliente_http(token_admin) as c:
        r = await c.post("/repuestos", json={"codigo": "H1", "descripcion": "Desc", "precio": "10.00", "stock": 0})
        rid = r.json()["id"]
    async with cliente_http(mecanico_token) as c:
        assert (await c.post("/repuestos", json={"codigo": "H2", "descripcion": "X", "precio": "1.00", "stock": 0})).status_code == 403
        assert (await c.patch(f"/repuestos/{rid}", json={"descripcion": "Y"})).status_code == 403
        assert (await c.delete(f"/repuestos/{rid}")).status_code == 403
        assert (await c.post(f"/repuestos/{rid}/reponer", json={"cantidad": 1})).status_code == 403


@pytest.mark.asyncio
async def test_no_autenticado_401(contexto_auth):
    async with cliente_http() as c:
        r = await c.get("/repuestos")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_stock_negativo_rechazado_422(contexto_auth):
    admin, token = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token) as c:
        r = await c.post("/repuestos", json={"codigo": "NEG1", "descripcion": "Neg", "precio": "1.00", "stock": -1})
        assert r.status_code == 422
