from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_TEST = RAIZ / "test"
DIR_TESTS = RAIZ / "tests"


def _archivos_de(directorio: Path) -> list[Path]:
    return [ruta for ruta in directorio.rglob("*") if ruta.is_file()]


def test_carpeta_test_no_contiene_archivos_python() -> None:
    assert list(DIR_TEST.rglob("*.py")) == []


def test_carpeta_test_contiene_un_unico_sql() -> None:
    assert len(list(DIR_TEST.rglob("*.sql"))) == 1


def test_carpeta_test_solo_contiene_archivos_http_y_sql() -> None:
    extensiones = {ruta.suffix for ruta in _archivos_de(DIR_TEST)}

    assert extensiones <= {".http", ".sql"}


def test_pytest_ini_declara_testpaths_tests() -> None:
    contenido = (RAIZ / "pytest.ini").read_text(encoding="utf-8")

    assert "testpaths = tests" in contenido


def test_carpeta_tests_contiene_conftest_y_al_menos_un_test() -> None:
    assert (DIR_TESTS / "conftest.py").is_file()
    assert list(DIR_TESTS.glob("test_*.py"))
