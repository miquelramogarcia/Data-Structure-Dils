import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from etl.fuentes import REGISTRO, mivau_35103500 as mu
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import TerritorioDesconocido, cargar_maestro

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)


@pytest.fixture(scope="module")
def resultado():
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        tabla = mu.transformar(FIXTURES / "35103500.xls", FECHA)
    return tabla, [str(a.message) for a in avisos if str(a.message).startswith("MIVAU-35103500")]


@pytest.fixture(scope="module")
def tabla(resultado):
    return resultado[0]


def _f(tabla, id_registro):
    return tabla.set_index("id_registro").loc[id_registro]


def test_registrada():
    f = REGISTRO["MIVAU-35103500"]
    assert f.TABLA == "mivau_valor_tasado_municipios_25000" and f.DIMENSIONES == ["antiguedad"]
    assert f.MEDIDAS == ["valor_tasado_eur_m2", "num_tasaciones"] and f.CUADRE is False


def test_valores_conocidos_formato_2005(tabla):
    f = _f(tabla, "MU04013_TOTAL_2005T1")  # Almería, hoja T1A2005, D20 y F20
    assert f["valor_tasado_eur_m2"] == 1477.4 and f["num_tasaciones"] == 867
    f = _f(tabla, "MU28079_TOTAL_2005T1")  # Madrid, T1A2005, D255 y F255
    assert f["valor_tasado_eur_m2"] == 3342.8 and f["num_tasaciones"] == 13970


def test_valores_conocidos_formato_2010_en_adelante(tabla):
    for ant, valor, n in (("HASTA_5_ANOS", 6205.3, 847), ("MAS_5_ANOS", 5395.0, 10839), ("TOTAL", 5418.4, 11686)):
        f = _f(tabla, f"MU28079_{ant}_2026T2")  # Madrid, T2A2026, D275/E275/F275 y H275/I275/J275
        assert f["valor_tasado_eur_m2"] == valor and f["num_tasaciones"] == n
    f = _f(tabla, "MU08019_TOTAL_2026T2")  # Barcelona, T2A2026, F142 y J142
    assert f["valor_tasado_eur_m2"] == 4601.8 and f["num_tasaciones"] == 5519


def test_nr_es_nulo_y_conserva_tasaciones(tabla):
    f = _f(tabla, "MU04066_HASTA_5_ANOS_2026T2")  # Níjar, T2A2026, D19 = 'n.r', H19 = 3
    assert pd.isna(f["valor_tasado_eur_m2"]) and f["num_tasaciones"] == 3


def test_madrid_y_barcelona_estan_en_todos_los_trimestres(tabla):
    for cod in ("MU28079", "MU08019"):
        t = tabla[(tabla["cod_territorio"] == cod) & (tabla["antiguedad"] == "TOTAL")]
        assert len(t) == 86 and t["valor_tasado_eur_m2"].notna().all()


def test_antiguedad_por_formato(tabla):
    assert tabla.groupby("antiguedad")["periodo"].min().to_dict() == {
        "TOTAL": "2005T1", "HASTA_5_ANOS": "2010T1", "MAS_5_ANOS": "2010T1"}
    assert len(tabla) == 63610 and tabla["cod_territorio"].nunique() == 306


def test_solo_municipios_con_codigos_ine_coherentes(tabla):
    assert set(tabla["nivel"]) == {"Municipio"}
    assert (tabla["cod_territorio"] == "MU" + tabla["cod_municipio"]).all()
    assert (tabla["cod_provincia"] == tabla["cod_municipio"].str[:2]).all()
    assert tabla["cod_ccaa"].notna().all() and tabla["nombre_ccaa"].notna().all()
    assert (tabla["provisional"] == 0).all()


def test_provincias_corregidas_exactas(resultado):
    # municipios que el boletín coloca tras la etiqueta de otra provincia (orden alfabético dentro de su grupo)
    tabla, avisos = resultado
    msg = " ".join(avisos)
    esperados = {"Almazora/Almassora": "Castellón/Castelló", "Almuñecar": "Granada", "Ames": "La Coruña",
                 "Azuqueca de Henares": "Guadalajara", "Benicarló": "Castellón/Castelló",
                 "Cangas": "Pontevedra", "Illescas": "Toledo"}
    assert len(avisos) == 1
    for m, p in esperados.items():
        assert f"'{m}': etiqueta heredada" in msg and f"es de '{p}'" in msg
    assert msg.count("etiqueta heredada") == len(esperados)
    f = _f(tabla, "MU18017_TOTAL_2026T2")  # Almuñécar: provincia 18 (Granada), no Córdoba
    assert f["nombre_provincia"] == "Granada"


def test_municipio_desconocido_falla_con_su_nombre_y_hoja():
    maestro = cargar_maestro(LIBRO)
    with pytest.raises(TerritorioDesconocido, match="Atlantis"):
        mu._resolver(maestro, "Almería", "Atlantis", "T1A2005")
    with pytest.raises(TerritorioDesconocido, match="T1A2005"):
        mu._resolver(maestro, "Almería", "Atlantis", "T1A2005")


def test_municipio_fuera_de_orden_no_listado_falla(monkeypatch):
    # Illescas es de Toledo: bajo la etiqueta Guadalajara y SIN estar en PROVINCIA_REAL, falla
    monkeypatch.delitem(mu.PROVINCIA_REAL, "Illescas")
    maestro = cargar_maestro(LIBRO)
    with pytest.raises(TerritorioDesconocido, match="Illescas"):
        mu._resolver(maestro, "Guadalajara", "Illescas", "T2A2026")
    # otro municipio real de otra provincia, sintético: Motril (Granada) bajo Córdoba
    with pytest.raises(TerritorioDesconocido, match="Motril"):
        mu._resolver(maestro, "Córdoba", "Motril", "T2A2026")


def test_lista_conocida_impone_la_provincia_real(monkeypatch):
    maestro = cargar_maestro(LIBRO)
    t, usada = mu._resolver(maestro, "Guadalajara", "Illescas")
    assert usada == "Toledo" and t["cod_territorio"] == "MU45081"
    # aunque el nombre exista también en la provincia heredada (homónimo), manda la real
    mun = maestro[(maestro["nivel"] == "Municipio") & (maestro["fuente_alias"] == "INE")]
    rep = mun[mun["alias"].duplicated(keep=False)].sort_values("alias")
    a, b = rep.iloc[0], rep.iloc[1]
    assert a["alias"] == b["alias"] and a["cod_provincia"] != b["cod_provincia"]
    monkeypatch.setitem(mu.PROVINCIA_REAL, a["nombre_municipio"], b["nombre_provincia"])
    t, usada = mu._resolver(maestro, a["nombre_provincia"], a["nombre_municipio"])
    assert usada == b["nombre_provincia"] and t["cod_territorio"] == b["cod_territorio"]


def test_lista_de_correcciones_exacta():
    assert mu.PROVINCIA_REAL == {
        "Almuñecar": "Granada", "Azuqueca de Henares": "Guadalajara", "Illescas": "Toledo", "Ames": "La Coruña",
        "Cangas": "Pontevedra", "Almazora/Almassora": "Castellón/Castelló", "Benicarló": "Castellón/Castelló"}


def test_tabla_valida(tabla):
    validar_o_fallar(tabla, mu.TABLA, cargar_maestro(LIBRO))
