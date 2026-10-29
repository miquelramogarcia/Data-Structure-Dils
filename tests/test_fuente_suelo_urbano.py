from datetime import date
from pathlib import Path

import pytest

from etl.fuentes import REGISTRO, mivau_36400500 as suelo
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import cargar_maestro

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)


@pytest.fixture(scope="module")
def tabla():
    return suelo.transformar(FIXTURES / "36400500.xls", FECHA)


def _v(tabla, id_registro):
    return tabla.set_index("id_registro").loc[id_registro, "precio_eur_m2"]


def test_registrada():
    assert REGISTRO["MIVAU-36400500"] is suelo
    assert suelo.DIMENSIONES == [] and suelo.MEDIDAS == ["precio_eur_m2"]
    assert suelo.CUADRE is False  # son precios medios: no se suman


def test_valores_conocidos(tabla):
    assert _v(tabla, "ES_2004T1") == 206.47   # celda C14 de la hoja "Tabla 4"
    assert _v(tabla, "ES_2026T2") == 207.76   # celda CN14 (última columna de trimestre)
    assert _v(tabla, "PR04_2026T2") == 215.09  # Almería, celda CN16
    assert _v(tabla, "PR04_2004T1") == 221.82  # Almería, celda C16
    assert _v(tabla, "PR28_2026T2") == _v(tabla, "CA13_2026T2")  # Madrid uniprovincial copiada


def test_forma(tabla):
    assert len(tabla) == 68 * 90 and tabla["id_registro"].is_unique
    assert tabla["periodo"].nunique() == 90
    assert tabla["provisional"].eq(0).all()
    ult = tabla[tabla["id_registro"] == "ES_2026T2"].iloc[0]
    assert (ult["frecuencia"], ult["anio"], ult["trimestre"], str(ult["fecha"])) == ("T", 2026, 2, "2026-04-01")


def test_ns_y_punto_son_nulos(tabla):
    # Teruel 2013T3 = "n.s." en el original; Avila 2007... hay celdas "." y "n.s"; nunca 0
    assert tabla["precio_eur_m2"].isna().sum() > 0
    assert (tabla["precio_eur_m2"].dropna() > 0).all()


def test_columnas_variacion_no_son_periodo(tabla):
    assert set(tabla["periodo"]) == {f"{a}T{t}" for a in range(2004, 2027) for t in range(1, 5)} - {"2026T3", "2026T4"}


def test_ceuta_y_melilla_agregado_no_entra(tabla):
    # Ceuta y Melilla solo viene juntas (sin código INE): ni CA18/CA19 ni PR51/PR52; quedan ES + 17 CCAA + 50 provincias
    una = tabla[tabla["periodo"] == "2026T2"]
    assert (una["nivel"] == "CCAA").sum() == 17 and (una["nivel"] == "Provincia").sum() == 50


def test_valida(tabla):
    validar_o_fallar(tabla, suelo.TABLA, cargar_maestro(LIBRO))
