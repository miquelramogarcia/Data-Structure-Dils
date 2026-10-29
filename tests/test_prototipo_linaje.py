"""Prototipo de mapeo origen -> destino y control de cargas (Tarea 18)."""
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from etl.catalogo.sql import cargar_catalogo
from prototipos.linaje import generar as g

RAIZ = Path(__file__).resolve().parent.parent
DIR = RAIZ / "prototipos" / "linaje"
COLUMNAS_MAPEO = ["tabla", "columna_destino", "dataset_id", "archivo_origen", "hoja_origen", "ubicacion_origen",
                  "transformacion", "regla"]


def _con_datos():
    tablas, campos = cargar_catalogo()
    t = set(tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]["tabla"])
    return t, campos[campos["tabla"].isin(t)]


def test_mapeo_cubre_todas_las_columnas_de_campos():
    mapeo = pd.read_csv(DIR / "mapeo.csv", sep=";", dtype=str, keep_default_na=False)
    assert list(mapeo.columns) == COLUMNAS_MAPEO
    _, campos = _con_datos()
    esperado = set(zip(campos["tabla"], campos["campo"]))
    hay = set(zip(mapeo["tabla"], mapeo["columna_destino"]))
    assert not esperado - hay, f"columnas sin mapeo: {sorted(esperado - hay)[:5]}"
    assert not hay - esperado, f"filas de mapeo sin columna en campos.csv: {sorted(hay - esperado)[:5]}"


def test_mapeo_sin_huecos_en_lo_esencial():
    mapeo = pd.read_csv(DIR / "mapeo.csv", sep=";", dtype=str, keep_default_na=False)
    for c in ("dataset_id", "archivo_origen", "ubicacion_origen", "transformacion"):
        assert (mapeo[c].str.strip() != "").all(), f"hay filas con {c} vacío"
    # los dataset_id citados existen en el catálogo
    tablas, _ = cargar_catalogo()
    ids = set(tablas["dataset_id"])
    usados = {i for v in mapeo["dataset_id"] for i in v.split(";")}
    assert usados <= ids, usados - ids


def test_mapeo_versionado_coincide_con_el_generador():
    generado = g.generar_mapeo()
    leido = pd.read_csv(DIR / "mapeo.csv", sep=";", dtype=str, keep_default_na=False)
    assert generado.fillna("").astype(str).reset_index(drop=True).equals(leido)


def test_mapeo_columnas_generadas_apuntan_a_fecha():
    mapeo = g.generar_mapeo()
    fila = mapeo[(mapeo["tabla"] == "mivau_vpo_calificaciones_definitivas") & (mapeo["columna_destino"] == "anio")]
    assert len(fila) == 1 and "YEAR(fecha)" in fila.iloc[0]["transformacion"]


def test_mapeo_ejemplo_concreto_vpo():
    m = g.generar_mapeo().set_index(["tabla", "columna_destino"])
    f = m.loc[("mivau_vpo_calificaciones_definitivas", "cod_territorio")]
    assert "resolver" in f["transformacion"] and f["dataset_id"] == "MIVAU-31205000"
    assert f["archivo_origen"] == "31205000.XLS" and f["hoja_origen"] == "Tabla 1.6"


def test_ddl_control_cargas_tiene_las_columnas_del_brief():
    cols = g.columnas_ddl()
    assert cols == ["id_carga", "dataset_id", "tabla", "url", "archivo", "hash_sha256_archivo", "fecha_descarga",
                    "inicio", "fin", "filas_leidas", "filas_escritas", "avisos_cuadre", "estado", "mensaje_error",
                    "version_codigo", "script"]
    sql = (DIR / "control_cargas.sql").read_text(encoding="utf-8")
    assert "`META`.`control_cargas`" in sql and "AUTO_INCREMENT" in sql and "PRIMARY KEY (`id_carga`)" in sql
    assert "ENUM('OK','ERROR')" in sql
    assert sql == g.generar_ddl()


def test_csv_ejemplo_tiene_todas_las_columnas_del_ddl():
    ejemplo = pd.read_csv(DIR / "control_cargas_ejemplo.csv", sep=";", dtype=str, keep_default_na=False)
    assert list(ejemplo.columns) == g.columnas_ddl()
    assert len(ejemplo) >= 1 and (ejemplo["estado"].isin(["OK", "ERROR"])).all()
    ok = ejemplo[ejemplo["estado"] == "OK"].iloc[0]
    assert re.fullmatch(r"[0-9a-f]{64}", ok["hash_sha256_archivo"]) and int(ok["filas_escritas"]) > 0


def _fuente(ok=True):
    def ejecutar(fecha):
        if not ok:
            raise ValueError("matriz rota")
        return pd.DataFrame({"x": [1, 2, 3]})
    return SimpleNamespace(DATASET_ID="D1", TABLA="t1", MEDIDAS=["x"], DIMENSIONES=[], CUADRE=False,
                           ejecutar=ejecutar)


def test_envoltorio_registra_ok_y_error(tmp_path, monkeypatch):
    archivo = tmp_path / "D1_20261029.xls"
    archivo.write_bytes(b"abc")
    monkeypatch.setattr(g, "REGISTRO", {"D1": _fuente(), "D2": _fuente(ok=False)})
    monkeypatch.setattr(g, "url_de", lambda i: f"http://x/{i}")
    destino = tmp_path / "c.csv"
    filas = g.ejecutar_con_control(["D1", "D2"], destino, archivos={"D1": archivo}, version="abc1234")
    assert [f["estado"] for f in filas] == ["OK", "ERROR"]
    ok, error = filas
    assert ok["filas_escritas"] == 3 and ok["tabla"] == "t1" and ok["version_codigo"] == "abc1234"
    assert ok["hash_sha256_archivo"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert ok["archivo"] == archivo.name and ok["avisos_cuadre"] is None and ok["fin"] >= ok["inicio"]
    assert error["mensaje_error"] == "matriz rota" and error["filas_escritas"] is None
    leido = pd.read_csv(destino, sep=";", dtype=str, keep_default_na=False)
    assert list(leido.columns) == g.columnas_ddl() and list(leido["id_carga"]) == ["1", "2"]
    # anexa: el siguiente id_carga continúa
    g.ejecutar_con_control(["D1"], destino, version="abc1234")
    assert list(pd.read_csv(destino, sep=";", dtype=str)["id_carga"]) == ["1", "2", "3"]


def test_envoltorio_no_toca_ejecutar_todo():
    import inspect

    from etl import ejecutar_todo
    assert "prototipos" not in inspect.getsource(ejecutar_todo)


def test_hoja_del_libro_mapeo():
    from prototipos.linaje import hoja_libro
    (nombre, df), = hoja_libro.hojas()
    assert nombre == "Mapeo (prototipo)" and list(df.columns) == COLUMNAS_MAPEO and len(df) > 100
