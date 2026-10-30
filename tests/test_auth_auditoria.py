import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.modules.usuarios.models import IntentoAcceso, EventoSeguridad
from app.modules.usuarios.repository import obtener_sesion_auditoria, registrar_intento, registrar_evento
from app.modules.usuarios.service import auditar_acceso, RegistroAcceso


@pytest.mark.asyncio
async def test_auditar_acceso_registra_intento_y_evento(contexto_auth):
    sesion = contexto_auth
    registro = RegistroAcceso(
        email="test@taller.test",
        ip="127.0.0.1",
        actor="test@taller.test",
        accion="LOGIN_FALLIDO",
        exito=False,
        cuando=datetime.now(timezone.utc),
    )
    await auditar_acceso(sesion, registro)

    intentos = (await sesion.execute(select(IntentoAcceso).where(IntentoAcceso.email == "test@taller.test"))).scalars().all()
    eventos = (await sesion.execute(select(EventoSeguridad).where(EventoSeguridad.actor == "test@taller.test"))).scalars().all()

    assert len(intentos) == 1
    assert intentos[0].exito is False
    assert len(eventos) == 1
    assert eventos[0].accion == "LOGIN_FALLIDO"


@pytest.mark.asyncio
async def test_auditar_acceso_bloqueado_no_inserta_intento(contexto_auth):
    sesion = contexto_auth
    registro = RegistroAcceso(
        email="bloqueado@taller.test",
        ip="127.0.0.1",
        actor="bloqueado@taller.test",
        accion="LOGIN_BLOQUEADO",
        exito=None,
        cuando=datetime.now(timezone.utc),
    )
    await auditar_acceso(sesion, registro)

    intentos = (await sesion.execute(select(IntentoAcceso).where(IntentoAcceso.email == "bloqueado@taller.test"))).scalars().all()
    eventos = (await sesion.execute(select(EventoSeguridad).where(EventoSeguridad.actor == "bloqueado@taller.test"))).scalars().all()

    assert len(intentos) == 0
    assert len(eventos) == 1
    assert eventos[0].accion == "LOGIN_BLOQUEADO"


@pytest.mark.asyncio
async def test_auditar_acceso_falla_propaga_excepcion():
    class SesionFalla:
        def begin(self):
            raise RuntimeError("Fallo de conexión en base de datos")

    registro = RegistroAcceso(
        email="error@taller.test",
        ip="127.0.0.1",
        actor="error@taller.test",
        accion="LOGIN_FALLIDO",
        exito=False,
    )
    with pytest.raises(RuntimeError) as exc_info:
        await auditar_acceso(SesionFalla(), registro)
    assert "Fallo de conexión" in str(exc_info.value)


@pytest.mark.asyncio
async def test_auditar_acceso_unitario_agrega_a_sesion():
    class ContextoTransaccion:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class SesionFake:
        def __init__(self):
            self.agregados = []
        def begin(self):
            return ContextoTransaccion()
        def add(self, item):
            self.agregados.append(item)

    sesion_fake = SesionFake()
    ahora = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
    registro = RegistroAcceso(
        email="fake@test.com",
        ip="192.168.1.1",
        actor="fake@test.com",
        accion="LOGIN_OK",
        exito=True,
        cuando=ahora,
    )
    await auditar_acceso(sesion_fake, registro)

    assert len(sesion_fake.agregados) == 2
    intento, evento = sesion_fake.agregados
    assert isinstance(intento, IntentoAcceso)
    assert intento.email == "fake@test.com"
    assert intento.exito is True
    assert isinstance(evento, EventoSeguridad)
    assert evento.accion == "LOGIN_OK"
