from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from etl.lib import mivau
from etl.lib.mivau import _parsear_valores, a_numero, descargar, leer_matriz, subperiodo

FIXTURE = Path(__file__).parent / "fixtures" / "31205000.xls"


def _matriz(filas):
    return pd.DataFrame(_parsear_valores("h", filas))


def test_leer_matriz_vpo():
    df = leer_matriz(FIXTURE)
    assert list(df.columns) == ["hoja", "territorio_txt", "anio", "subperiodo_txt", "valor_txt"]
    f = df[(df.territorio_txt.str.strip() == "TOTAL NACIONAL") & (df.anio == 2008)
           & (df.subperiodo_txt == "Ene.")]
    assert len(f) == 1
    assert a_numero(f.iloc[0].valor_txt) == 4918


def test_leer_matriz_vpo_dimensiones():
    df = leer_matriz(FIXTURE)
    assert len(df) == 13986
    assert df.territorio_txt.nunique() == 63
    assert df.anio.min() == 2008 and df.anio.max() == 2026


def test_valor_vacio_es_nulo():
    assert a_numero("-") is None
    assert a_numero("..") is None
    assert a_numero(".") is None
    assert a_numero("") is None
    assert a_numero("ND") is None
    assert a_numero("0") == 0.0
    assert a_numero("124201.8") == 124201.8


def test_columna_total_ignorada():
    filas = [
        ["", "", "Año 2020", "", "", "", ""],
        ["", "", "1º", "2º", "Total", "Media", ""],
        ["", "España", 1.0, 2.0, 3.0, 1.5, ""],
    ]
    df = _matriz(filas)
    assert sorted(df.subperiodo_txt) == ["1º", "2º"]
    assert not leer_matriz(FIXTURE).subperiodo_txt.str.lower().isin(["total", "media", "año"]).any()


def test_subperiodo_trimestre():
    assert subperiodo("3º T") == ("T", 3)
    assert subperiodo("Ene.") == ("M", 1)
    assert subperiodo("1T") == ("T", 1)
    assert subperiodo("Trimestre 2") == ("T", 2)
    assert subperiodo("IV") == ("T", 4)
    assert subperiodo("2º") == ("T", 2)
    assert subperiodo("Sept.") == ("M", 9)
    for malo in ("Total", "Media", "Año", "Mario", "(trimestre)"):
        with pytest.raises(ValueError):
            subperiodo(malo)


def test_blanco_en_la_rejilla_y_texto_pasan_a_nulo():
    filas = [
        ["", "", "Año 2020", "", "", ""],
        ["", "", "Ene.", "Feb.", "Mar.", "Abr."],
        ["", "A", 1.0, "", "ND", ""],
        ["", "B", "-", "-", "", ""],
        ["", "C", "", "", "", ""],
        ["", "Fuente: MIVAU", 9.0, "", "", ""],
        ["", "D", 5.0, 5.0, 5.0, ""],
    ]
    df = _matriz(filas)
    # Abr. no tiene ningún valor (relleno): se salta. C (sin celdas) y lo posterior al pie, fuera.
    assert sorted(df.territorio_txt.unique()) == ["A", "B"]
    a = df[df.territorio_txt == "A"].set_index("subperiodo_txt").valor_txt
    assert list(a.index) == ["Ene.", "Feb.", "Mar."]
    assert a["Ene."] == "1" and a["Feb."] == "" and a["Mar."] == "ND"
    assert a_numero(a["Feb."]) is None and a_numero(a["Mar."]) is None
    b = df[df.territorio_txt == "B"]
    assert len(b) == 3 and all(a_numero(v) is None for v in b.valor_txt)


def test_errores_descriptivos():
    with pytest.raises(ValueError, match="'h'"):
        _parsear_valores("h", [["", "nada"]])
    with pytest.raises(ValueError, match="'h'"):
        _parsear_valores("h", [["", "", "2020", ""], ["", "", "Ene.", "Feb."]])
    with pytest.raises(ValueError, match="Inexistente"):
        leer_matriz(FIXTURE, hojas=["Inexistente"])


class _Resp:
    def __init__(self, status, content=b"datos"):
        self.status_code, self.content = status, content


def test_descargar(tmp_path, monkeypatch):
    llamadas = []

    def falso(url, headers=None, timeout=None):
        llamadas.append((url, timeout))
        return _Resp(200)

    monkeypatch.setattr(mivau.requests, "get", falso)
    ruta = descargar("https://x.es/a/31205000.XLS", "31205000", tmp_path)
    assert ruta.name == f"31205000_{date.today():%Y%m%d}.xls"
    assert ruta.read_bytes() == b"datos" and llamadas[0][1] == 60
    assert descargar("https://x.es/a/31205000.XLS", "31205000", tmp_path) == ruta
    assert len(llamadas) == 1  # el del día no se vuelve a descargar


def test_descargar_no_200_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(mivau.requests, "get", lambda *a, **k: _Resp(404))
    with pytest.raises(RuntimeError):
        descargar("https://x.es/a/otro.XLS", "otro", tmp_path)
    assert not list(tmp_path.iterdir())
