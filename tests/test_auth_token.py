from datetime import datetime, timedelta, timezone
import pytest
import jwt
from app.core.configuracion import configuracion
from app.core.seguridad import crear_token_acceso, decodificar_token_acceso
from app.core.errors import NoAutenticadoError


def test_crear_token_acceso_contiene_claims_esperados():
    ahora = datetime.now(timezone.utc)
    token = crear_token_acceso(usuario_id=1, roles=["ADMIN"], iat=ahora)
    
    # Con verify_iat=False para que pyjwt no exija int en iat (D6 usa ISO-8601)
    payload = jwt.decode(
        token,
        configuracion.jwt_secret,
        algorithms=["HS256"],
        options={"verify_signature": True, "verify_iat": False, "verify_exp": False},
    )
    assert payload["sub"] == "1"
    assert payload["roles"] == ["ADMIN"]
    assert "iat" in payload
    assert "exp" in payload


def test_crear_token_acceso_exp_exacto_segun_ttl():
    ahora = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
    token = crear_token_acceso(usuario_id=42, roles=["MECANICO", "RECEPCIONISTA"], iat=ahora)
    payload = jwt.decode(
        token,
        configuracion.jwt_secret,
        algorithms=["HS256"],
        options={"verify_signature": True, "verify_iat": False, "verify_exp": False},
    )
    esperado_exp = int(ahora.timestamp()) + configuracion.access_token_ttl_min * 60
    assert payload["sub"] == "42"
    assert payload["roles"] == ["MECANICO", "RECEPCIONISTA"]
    assert payload["exp"] == esperado_exp


def test_crear_token_acceso_conserva_microsegundos_en_iat():
    ahora_con_microsegundos = datetime(2026, 10, 30, 15, 30, 45, 123456, tzinfo=timezone.utc)
    token = crear_token_acceso(usuario_id=99, roles=[], iat=ahora_con_microsegundos)
    payload = jwt.decode(
        token,
        configuracion.jwt_secret,
        algorithms=["HS256"],
        options={"verify_signature": True, "verify_iat": False, "verify_exp": False},
    )
    recuperado = datetime.fromisoformat(payload["iat"])
    assert recuperado == ahora_con_microsegundos
    assert recuperado.microsecond == 123456


def test_decodificar_token_valido():
    ahora = datetime.now(timezone.utc)
    token = crear_token_acceso(usuario_id=1, roles=["ADMIN"], iat=ahora)
    datos = decodificar_token_acceso(token)
    assert datos["sub"] == "1"
    assert datos["roles"] == ["ADMIN"]
    assert isinstance(datos["iat"], datetime)
    assert datos["iat"] == ahora


def test_decodificar_token_firma_invalida():
    token = crear_token_acceso(usuario_id=1, roles=[], iat=datetime.now(timezone.utc))
    token_manipulado = token[:-4] + "fake"
    with pytest.raises(NoAutenticadoError) as exc_info:
        decodificar_token_acceso(token_manipulado)
    assert exc_info.value.codigo == "CREDENCIALES_INVALIDAS"


def test_decodificar_token_expirado():
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    token = crear_token_acceso(usuario_id=1, roles=[], iat=hace_dos_horas)
    with pytest.raises(NoAutenticadoError) as exc_info:
        decodificar_token_acceso(token)
    assert exc_info.value.codigo == "CREDENCIALES_INVALIDAS"


def test_decodificar_token_algoritmo_no_permitido():
    token_none = jwt.encode({"sub": "1", "exp": 9999999999, "iat": "2026-10-30T12:00:00+00:00"}, key="", algorithm="none")
    with pytest.raises(NoAutenticadoError):
        decodificar_token_acceso(token_none)


def test_decodificar_token_sin_iat():
    token_sin_iat = jwt.encode({"sub": "1", "exp": 9999999999}, key=configuracion.jwt_secret, algorithm="HS256")
    with pytest.raises(NoAutenticadoError):
        decodificar_token_acceso(token_sin_iat)
