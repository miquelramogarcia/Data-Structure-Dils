from datetime import date
from pathlib import Path

import pytest

from etl.fuentes import REGISTRO, mivau_34010110 as transacciones, mivau_340101g0 as extranjeros
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import cargar_maestro
from etl.lib.validar import cuadre_jerarquico

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)


@pytest.fixture(scope="module")
def t_total():
    return transacciones.transformar(FIXTURES / "34010110.xls", FECHA)


@pytest.fixture(scope="module")
def t_ext():
    return extranjeros.transformar(FIXTURES / "340101g0.xls", FECHA)


def _v(tabla, id_registro):
    return tabla.set_index("id_registro").loc[id_registro, "num_transacciones"]


def test_registradas():
    assert REGISTRO["MIVAU-34010110"] is transacciones and REGISTRO["MIVAU-340101g0"] is extranjeros
    assert transacciones.DIMENSIONES == [] and transacciones.MEDIDAS == ["num_transacciones"]
    assert extranjeros.DIMENSIONES == ["cod_ccaa_comprador"] and extranjeros.MEDIDAS == ["num_transacciones"]


def test_transacciones_valores_conocidos(t_total):
    assert _v(t_total, "ES_2004T1") == 190442  # celda C15 de la primera hoja ("2004, ..., 2008")
    assert _v(t_total, "ES_2026T2") == 182637  # celda L15 de la última hoja ("2024, 2025, 2026")
    assert _v(t_total, "PR04_2026T2") == 4365  # Almería, celda L17 de la última hoja
    assert _v(t_total, "PR28_2026T2") == _v(t_total, "CA13_2026T2") == 20225  # Madrid: uniprovincial copiada


def test_transacciones_forma_y_provisional(t_total):
    assert len(t_total) == 72 * 90 and t_total["id_registro"].is_unique
    assert t_total["periodo"].nunique() == 90
    prov = t_total[t_total["provisional"] == 1]["periodo"].unique().tolist()
    assert prov == ["2026T2"]  # "2º (**)" en la cabecera de la última hoja
    ult = t_total[t_total["id_registro"] == "ES_2026T2"].iloc[0]
    assert (ult["frecuencia"], ult["anio"], ult["trimestre"], str(ult["fecha"])) == ("T", 2026, 2, "2026-04-01")
    assert t_total["mes"].isna().all()
    assert "CA19" in set(t_total["cod_territorio"]) and "PR52" in set(t_total["cod_territorio"])


def test_ceuta_y_melilla_agregado_no_entra(t_total):
    # "Ceuta y Melilla" no tiene código INE: Ceuta y Melilla van por separado
    una = t_total[t_total["periodo"] == "2026T2"]
    assert (una["nivel"] == "CCAA").sum() == 19 and (una["nivel"] == "Provincia").sum() == 52


def test_extranjeros_valores_conocidos(t_ext):
    assert _v(t_ext, "ES_00_2007T1") == 10708  # hoja "1t 2007", C16: vivienda España, residentes en España
    assert _v(t_ext, "ES_00_2026T2") == 18142  # hoja "2t 2026", C16
    assert _v(t_ext, "CA01_01_2026T2") == 2773  # Andalucía/Andalucía, hoja "2t 2026", D17
    assert _v(t_ext, "CA10_01_2026T2") == 18  # vivienda Comunitat Valenciana, comprador andaluz, D26 hoja "2t 2026"
    assert _v(t_ext, "PR28_13_2026T2") == _v(t_ext, "CA13_13_2026T2") == 1612  # Madrid (uniprovincial), P29


def test_extranjeros_forma_y_compradores(t_ext):
    assert len(t_ext) == 25 * 19 * 78 and t_ext["id_registro"].is_unique
    comp = t_ext[["cod_ccaa_comprador", "nombre_ccaa_comprador"]].drop_duplicates()
    assert len(comp) == 19
    nombres = dict(zip(comp["cod_ccaa_comprador"], comp["nombre_ccaa_comprador"]))
    assert nombres["00"] == "Total residentes en España" and nombres["99"] == "Ceuta y Melilla"
    assert nombres["16"] == "País Vasco" and nombres["08"] == "Castilla - La Mancha"
    assert sorted(set(t_ext["cod_ccaa_comprador"])) == ["00"] + [f"{i:02d}" for i in range(1, 18)] + ["99"]
    assert sorted(t_ext[t_ext["provisional"] == 1]["periodo"].unique()) == ["2025T3", "2026T2"]
    # España x Ceuta y Melilla compradores: celda en blanco (U16) de la hoja "3t 2007" → NULL, no 0
    assert t_ext.set_index("id_registro").loc["ES_99_2007T3", "num_transacciones"] is None or \
        t_ext.set_index("id_registro")["num_transacciones"].isna().loc["ES_99_2007T3"]
    assert _v(t_ext, "ES_99_2007T1") == 6  # U16 de la hoja "1t 2007"
    assert "CA18" not in set(t_ext["cod_territorio"])  # el agregado "Ceuta y Melilla" de vivienda no entra


def test_validacion_limpia(t_total, t_ext):
    maestro = cargar_maestro(LIBRO)
    validar_o_fallar(t_total, transacciones.TABLA, maestro)
    validar_o_fallar(t_ext, extranjeros.TABLA, maestro)


def test_cuadre_transacciones_sin_excepciones(t_total):
    # Nacional = suma de CCAA y CCAA = suma de provincias en los 90 trimestres (Ceuta y Melilla van aparte)
    assert cuadre_jerarquico(t_total, "num_transacciones", []).empty


def _hojas_extranjeros():
    """{(anio, trimestre): hoja xlrd} leídas del .xls original."""
    import xlrd
    wb = xlrd.open_workbook(str(FIXTURES / "340101g0.xls"))
    return {(int(h.name.split()[1]), int(h.name[0])): h for h in wb.sheets()}


def test_cuadre_extranjeros_excepciones_exactas(t_ext):
    # Oráculo independiente del ETL, leído del .xls: para cada trimestre y comprador, fila "España" (fila 16 de
    # Excel) menos la suma de las 17 comunidades (filas 17-33 salvo "Ceuta y Melilla", fila 34).
    # La diferencia es, por construcción, la celda de "Ceuta y Melilla" de la vivienda (omitida: sin código INE)
    # y, en las 22 hojas donde "España" x comprador "Ceuta y Melilla" está en blanco (NULL), también esa celda.
    esperado = {}
    for (anio, trim), h in _hojas_extranjeros().items():
        assert h.cell_value(33, 1).strip() == "Ceuta y Melilla"
        for col in range(2, 21):
            esp = h.cell_value(15, col)
            esp = 0.0 if esp == "" else esp
            hijos = sum(h.cell_value(r, col) for r in range(16, 33) if h.cell_value(r, col) != "")
            if abs(esp - hijos) > 1e-6:
                cod = "00" if col == 2 else "99" if col == 20 else f"{col - 2:02d}"
                esperado[(f"{anio}T{trim}", cod)] = esp - hijos
    real = cuadre_jerarquico(t_ext, "num_transacciones", ["cod_ccaa_comprador"])
    assert set(real["nivel_padre"]) == {"Nacional"} and set(real["cod_padre"]) == {"ES"}
    assert {(r.periodo, r.cod_ccaa_comprador): r.diferencia for r in real.itertuples()} == esperado
    assert len(esperado) == 193
    ceuta_melilla = {(f"{a}T{t}", "99"): h.cell_value(15, 20) for (a, t), h in _hojas_extranjeros().items()}
    assert sum(1 for v in ceuta_melilla.values() if v == "") == 22


def test_extranjeros_total_comprador_es_suma_de_compradores(t_ext):
    # "00" (residentes en España) = suma del resto de compradores, salvo ES x "99" en blanco (22 trimestres, NULL)
    t = t_ext.assign(v=t_ext["num_transacciones"].astype("float").fillna(0))
    total = t[t["cod_ccaa_comprador"] == "00"].set_index(["cod_territorio", "periodo"])["v"]
    resto = t[t["cod_ccaa_comprador"] != "00"].groupby(["cod_territorio", "periodo"])["v"].sum()
    dif = (total - resto)[(total - resto) != 0]
    assert len(dif) == 22 and set(dif.index.get_level_values("cod_territorio")) == {"ES"}
    nulos = t_ext[(t_ext["cod_territorio"] == "ES") & (t_ext["cod_ccaa_comprador"] == "99")
                  & t_ext["num_transacciones"].isna()]
    assert sorted(dif.index.get_level_values("periodo")) == sorted(nulos["periodo"])
