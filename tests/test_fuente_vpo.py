from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from etl.catalogo.sql import cargar_catalogo
from etl.fuentes import REGISTRO, mivau_31205000 as vpo
from etl.lib.fuente_comun import escribir_csv
from etl.lib.territorios import cargar_maestro, leer_hoja_usuario
from etl.lib.validar import validar_tabla

RAIZ = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "31205000.xls"
LIBRO = RAIZ / "Data Dils.xlsx"
FECHA = date(2026, 10, 29)


@pytest.fixture(scope="module")
def tabla():
    return vpo.transformar(FIXTURE, FECHA)


def _valor(tabla, id_registro):
    return tabla.set_index("id_registro").loc[id_registro, "num_viviendas"]


def test_vpo_registrada():
    assert REGISTRO[vpo.DATASET_ID] is vpo
    assert vpo.TABLA == "mivau_vpo_calificaciones_definitivas"


def test_vpo_valores_conocidos(tabla):
    assert _valor(tabla, "ES_TOTAL_2008M01") == 4918
    assert _valor(tabla, "ES_TOTAL_2008M02") == 5075


def test_vpo_tamano_y_tipos(tabla):
    assert len(tabla) == 13986 + 9 * 222
    assert (tabla["regimen"] == "TOTAL").all() and (tabla["provisional"] == 0).all()
    assert str(tabla["num_viviendas"].dtype) == "Int64"


def test_vpo_uniprovinciales(tabla):
    ultimo = tabla["periodo"].max()
    assert _valor(tabla, f"PR28_TOTAL_{ultimo}") == _valor(tabla, f"CA13_TOTAL_{ultimo}")


def test_vpo_validacion_limpia(tabla):
    _, campos = cargar_catalogo()
    campos = campos[campos["tabla"] == vpo.TABLA]
    assert validar_tabla(tabla, campos, cargar_maestro(LIBRO)) == []


def test_vpo_escribe_csv_iso(tabla, tmp_path):
    ruta = escribir_csv(tabla, vpo.TABLA, tmp_path)
    leido = pd.read_csv(ruta, sep=";", dtype=str, encoding="utf-8")
    assert leido["fecha"].iloc[0] == "2008-01-01" and leido["fecha_descarga"].iloc[0] == "2026-10-29"


def test_vpo_coincide_con_hoja_actual(tabla):
    hoja = leer_hoja_usuario(LIBRO, "mivau_vpo_calificaciones_defini", dtype=str)
    hoja = hoja[hoja["nivel"].isin(["Nacional", "CCAA"])]
    nuevo = tabla.set_index("id_registro")["num_viviendas"]
    hoja_val = pd.to_numeric(hoja.set_index("id_registro")["num_viviendas"], errors="coerce")
    faltan = [i for i in hoja_val.index if i not in nuevo.index]
    comunes = hoja_val.index.intersection(nuevo.index)
    dif = [(i, hoja_val[i], nuevo[i]) for i in comunes
           if not (pd.isna(hoja_val[i]) and pd.isna(nuevo[i])) and hoja_val[i] != nuevo[i]]
    assert not faltan, f"{len(faltan)} id_registro de la hoja no están en el CSV: {faltan[:10]}"
    assert not dif, f"{len(dif)} diferencias (id, hoja, nuevo): {dif[:20]}"
