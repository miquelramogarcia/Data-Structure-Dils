from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from etl.fuentes import REGISTRO, mivau_valor_tasado as vt
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import cargar_maestro

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)
IDS = ["MIVAU-35101000", "MIVAU-35101500", "MIVAU-35102000"]


@pytest.fixture(scope="module")
def tabla():
    return vt.transformar({i: FIXTURES / f"{i.split('-')[1]}.xls" for i in IDS}, FECHA)


def _v(tabla, id_registro):
    return tabla.set_index("id_registro")["valor_tasado_eur_m2"].loc[id_registro]


def test_registradas_las_tres_en_una_tabla():
    for i in IDS:
        f = REGISTRO[i]
        assert f.DATASET_ID == i and f.TABLA == "mivau_valor_tasado_vivienda_libre"
        assert f.DIMENSIONES == ["antiguedad"] and f.MEDIDAS == ["valor_tasado_eur_m2"]
        assert f.CUADRE is False  # los valores medios no suman
        assert f.ejecutar is vt.ejecutar


def test_valores_conocidos_total(tabla):
    assert _v(tabla, "ES_TOTAL_1995T1") == 670.8  # 35101000, hoja "1995, ..., 1998", C15
    assert _v(tabla, "ES_TOTAL_2026T2") == 2355.0  # 35101000, hoja "2023, ..., 2026", P15
    assert _v(tabla, "PR04_TOTAL_2026T2") == 1492.6  # Almería, P17


def test_valores_conocidos_hasta_5_anos(tabla):
    assert _v(tabla, "ES_HASTA_5_ANOS_2010T1") == 2138.0  # 35101500, hoja "2010, ..., 2014", C16
    assert _v(tabla, "ES_HASTA_5_ANOS_2026T2") == 2736.6  # 35101500, hoja "2024, 2025, 2026", L16
    assert _v(tabla, "PR04_HASTA_5_ANOS_2026T2") == 1938.1  # Almería, L18


def test_valores_conocidos_mas_5_anos(tabla):
    assert _v(tabla, "ES_MAS_5_ANOS_2010T1") == 1835.5  # 35102000, C16
    assert _v(tabla, "ES_MAS_5_ANOS_2026T2") == 2342.5  # 35102000, L16
    assert _v(tabla, "PR04_MAS_5_ANOS_2026T2") == 1481.5  # Almería, L18


def test_nr_es_nulo(tabla):
    assert pd.isna(_v(tabla, "PR44_HASTA_5_ANOS_2012T2"))  # Teruel, 35101500 "2010...2014", L28 = 'n.r'
    assert pd.isna(_v(tabla, "PR51_HASTA_5_ANOS_2026T2"))  # Ceuta, L78 = 'n.r'
    assert _v(tabla, "PR44_HASTA_5_ANOS_2012T1") == 1519.9  # el trimestre anterior sí tiene dato (K28)


def test_columnas_de_variacion_no_son_periodos(tabla):
    assert set(tabla["frecuencia"]) == {"T"}
    assert tabla["periodo"].str.fullmatch(r"\d{4}T[1-4]").all()
    assert tabla.groupby("antiguedad")["periodo"].min().to_dict() == {
        "TOTAL": "1995T1", "HASTA_5_ANOS": "2010T1", "MAS_5_ANOS": "2010T1"}
    assert tabla.groupby("antiguedad")["periodo"].max().eq("2026T2").all()


def test_ceuta_y_melilla_agregado_no_se_carga_pero_ceuta_si(tabla):
    assert _v(tabla, "CA18_TOTAL_2026T2") == 2214.9  # Ceuta, P77
    assert _v(tabla, "PR51_TOTAL_2026T2") == 2214.9  # provincia generada desde la CCAA uniprovincial
    assert not tabla["nombre_ccaa"].str.contains("Ceuta y Melilla").any()


def test_provisional_siempre_cero(tabla):
    assert (tabla["provisional"] == 0).all()


def test_tabla_valida(tabla):
    validar_o_fallar(tabla, vt.TABLA, cargar_maestro(LIBRO))


def test_tabla_final_redondea_decimales_a_la_escala_del_catalogo():
    from datetime import date
    from etl.lib.fuente_comun import tabla_final
    from etl.lib.periodos import periodo_trimestral
    from etl.lib.territorios import cargar_maestro
    from etl.lib.fuente_comun import LIBRO
    maestro = cargar_maestro(LIBRO)
    fila = {**maestro[maestro["cod_territorio"] == "ES"].iloc[0][
        ["nivel", "cod_territorio", "cod_ccaa", "nombre_ccaa", "cod_provincia", "nombre_provincia",
         "cod_municipio", "nombre_municipio"]].to_dict(),
        "antiguedad": "TOTAL", **periodo_trimestral(2026, 1), "valor_tasado_eur_m2": 1459.3000000000002,
        "provisional": 0}
    t = tabla_final(pd.DataFrame([fila]), "X", "mivau_valor_tasado_vivienda_libre", ["antiguedad"],
                    "valor_tasado_eur_m2", maestro, date(2026, 10, 29), entero=False)
    assert t.loc[0, "valor_tasado_eur_m2"] == 1459.3
    assert "1459.3000000000002" not in t.to_csv(sep=";", index=False)
