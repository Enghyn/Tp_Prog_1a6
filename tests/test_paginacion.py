from app.core.paginacion import ParametrosPagina, Pagina


def test_parametros_pagina_por_defecto():
    params = ParametrosPagina()
    assert params.pagina == 1
    assert params.tamanio == 10


def test_parametros_pagina_validacion():
    params = ParametrosPagina(pagina=2, tamanio=50)
    assert params.pagina == 2
    assert params.tamanio == 50


def test_serializacion_pagina():
    pagina = Pagina(items=[{"id": 1}], total=1, pagina=1, tamanio=10)
    datos = pagina.model_dump()
    assert datos["items"] == [{"id": 1}]
    assert datos["total"] == 1
    assert datos["pagina"] == 1
    assert datos["tamanio"] == 10
