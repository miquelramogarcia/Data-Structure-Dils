from datetime import date
from pathlib import Path

import pytest

from etl.fuentes import REGISTRO, mivau_32100500 as iniciadas, mivau_32101000 as terminadas
from etl.lib.fuente_comun import LIBRO
from etl.lib.territorios import cargar_maestro
from etl.lib.validar import cuadre_jerarquico

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)

# (módulo, fichero, ES 2008M01 = celda C13, ES 2026M06 = celda HP13)
CASOS = [(iniciadas, "32100500.xls", 31829, 10369), (terminadas, "32101000.xls", 50337, 7552)]


@pytest.fixture(scope="module")
def tablas():
    return {m.DATASET_ID: m.transformar(FIXTURES / f, FECHA) for m, f, _, _ in CASOS}


def _valor(tabla, id_registro):
    return tabla.set_index("id_registro").loc[id_registro, "num_viviendas"]


@pytest.mark.parametrize("mod,fichero,primero,ultimo", CASOS)
def test_registrada_y_sin_dimensiones(mod, fichero, primero, ultimo):
    assert REGISTRO[mod.DATASET_ID] is mod
    assert mod.DIMENSIONES == [] and mod.MEDIDAS == ["num_viviendas"]


@pytest.mark.parametrize("mod,fichero,primero,ultimo", CASOS)
def test_valores_conocidos(tablas, mod, fichero, primero, ultimo):
    t = tablas[mod.DATASET_ID]
    assert _valor(t, "ES_2008M01") == primero
    assert _valor(t, "ES_2026M06") == ultimo


@pytest.mark.parametrize("mod,fichero,primero,ultimo", CASOS)
def test_tamano_y_uniprovinciales(tablas, mod, fichero, primero, ultimo):
    t = tablas[mod.DATASET_ID]
    assert len(t) == 13986 + 9 * 222
    assert t["id_registro"].is_unique and (t["provisional"] == 0).all()
    assert _valor(t, "PR28_2026M06") == _valor(t, "CA13_2026M06")
    assert str(t["num_viviendas"].dtype) == "Int64"


def test_nd_es_nulo_y_cero_se_conserva(tablas):
    t = tablas[iniciadas.DATASET_ID]
    soria = t[(t["cod_territorio"] == "PR42") & (t["periodo"].isin(["2026M01", "2026M02", "2026M03"]))]
    assert len(soria) == 3 and soria["num_viviendas"].isna().all()  # 'ND' en la fuente (celdas HK40:HM40)
    ceuta = t[(t["cod_ccaa"] == "18") & (t["periodo"] == "2008M01")]
    assert (ceuta["num_viviendas"] == 0).all() and len(ceuta) >= 1  # Ceuta 0 literal (fila 74)


def test_validacion_limpia(tablas):
    # transformar() ya valida (falla si no); se vuelve a comprobar de forma explícita
    from etl.lib.fuente_comun import validar_o_fallar
    maestro = cargar_maestro(LIBRO)
    for m, *_ in CASOS:
        validar_o_fallar(tablas[m.DATASET_ID], m.TABLA, maestro)


def test_cuadre_jerarquico_documentado(tablas):
    # Terminadas cuadra siempre. Iniciadas: únicas excepciones, País Vasco (CA16) 2008M10 y 2008M11, con
    # diferencia de +-1 vivienda entre la CCAA y la suma de sus provincias (redondeo de la fuente).
    assert cuadre_jerarquico(tablas[terminadas.DATASET_ID], "num_viviendas", []).empty
    av = cuadre_jerarquico(tablas[iniciadas.DATASET_ID], "num_viviendas", [])
    assert [(r.cod_padre, r.periodo, r.diferencia) for r in av.itertuples()] == [
        ("CA16", "2008M10", -1.0), ("CA16", "2008M11", 1.0)]
