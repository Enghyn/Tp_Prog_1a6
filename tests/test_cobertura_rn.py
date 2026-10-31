"""Verifica que cada regla RN-01..RN-20 tiene al menos un test que la ejerce."""

import importlib

import pytest

# Mapa RN -> lista de (modulo, nombre_de_test) que ejercen la regla.
COBERTURA_RN: dict[str, list[tuple[str, str]]] = {
    "RN-01": [("tests.test_auth_models", "test_usuario_email_unico")],
    "RN-02": [("tests.test_registro_atomico", "test_registro_exitoso_201_y_persistencia")],
    "RN-03": [("tests.test_admin_asignacion_rol", "test_doble_asignacion_vigente_devuelve_409_sin_alterar_la_original")],
    "RN-04": [("tests.test_autorizacion_rbac", "test_require_roles_claim_del_token_no_autoriza")],
    "RN-05": [("tests.test_admin_asignacion_rol", "test_revocar_propio_rol_admin_devuelve_409")],
    "RN-06": [("tests.test_autorizacion_rbac", "test_password_pendiente_bloquea_ruta_de_dominio")],
    "RN-07": [("tests.test_auth_rn07_integracion", "test_cambiar_password_invalida_el_token_anterior")],
    "RN-08": [("tests.test_auth_rate_limit", "test_rate_limit_bloqueo_429_y_retry_after")],
    "RN-09": [("tests.test_auth_login", "test_login_opaco_email_inexistente_vs_password_erronea_son_identicos")],
    "RN-10": [("tests.test_ordenes_apertura", "test_post_orden_total_calculado_ignora_precio_enviado")],
    "RN-11": [("tests.test_ordenes_transiciones", "test_iniciar_transicion_invalida_409")],
    "RN-12": [("tests.test_ordenes_transiciones", "test_cancelar_ajena_403")],
    "RN-13": [("tests.test_ordenes_transiciones", "test_terminar_exito_descuenta_stock_y_movimiento")],
    "RN-14": [("tests.test_repuestos_stock", "test_patch_stock_no_editable_422")],
    "RN-15": [("tests.test_solo_agregado", "test_historial_estado_orden_update_bloqueado")],
    "RN-16": [("tests.test_clientes_vehiculos", "test_delete_vehiculo_con_orden_abierta_409")],
    "RN-17": [("tests.test_autorizacion_rbac", "test_duenio_de_orden_ajena")],
    "RN-18": [("tests.test_errores", "test_formato_error_uniforme")],
    "RN-19": [("tests.test_ordenes_apertura", "test_post_orden_catalogo_vacio_409")],
    "RN-20": [("tests.test_repuestos_stock", "test_patch_descripcion_y_precio_genera_historial")],
}


def _existe_test(modulo: str, nombre: str) -> bool:
    try:
        mod = importlib.import_module(modulo)
    except Exception:
        return False
    obj = getattr(mod, nombre, None)
    return callable(obj)


@pytest.mark.parametrize("rn", sorted(COBERTURA_RN.keys()))
def test_cobertura_rn(rn: str):
    candidatos = COBERTURA_RN[rn]
    faltantes = [(m, n) for (m, n) in candidatos if not _existe_test(m, n)]
    # Se considera cubierta si al menos un candidato existe.
    cubiertos = [c for c in candidatos if _existe_test(*c)]
    assert cubiertos, f"{rn} sin cobertura: ninguno de {candidatos} existe"


# Verificacion adicional: todos los RN-01..RN-20 estan en el mapa.
def test_mapa_completo():
    esperados = {f"RN-{i:02d}" for i in range(1, 21)}
    assert set(COBERTURA_RN.keys()) == esperados
