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


def test_subperiodo_con_marca_de_provisional():
    assert subperiodo("2º (**)") == ("T", 2)
    assert subperiodo("Ene. (*)") == ("M", 1)
    assert mivau.marca_provisional("2º (**)") is True
    assert mivau.marca_provisional("2º") is False
    assert mivau.marca_provisional("Ene. (p)") is True


def test_cabecera_con_marca_de_provisional_no_pierde_columna():
    filas = [
        ["", "", "Año 2026", "", ""],
        ["", "", "(trimestre)", "", ""],
        ["", "", "1º", "2º (**)", ""],
        ["", "A", 1.0, 2.0, ""],
    ]
    df = _matriz(filas)
    assert list(df.subperiodo_txt) == ["1º", "2º (**)"]


FIXTURE_G0 = Path(__file__).parent / "fixtures" / "340101g0.xls"


def _hoja_cruzada(extra_pie=None):
    filas = [
        ["", "", "", "", ""],
        ["", "Tabla X.", "", "", ""],
        ["", "(**) Segundo trimestre de 2026", "", "", ""],
        ["", "Lugar de residencia comprador/", "Residentes", "Residentes en cada una", ""],
        ["", "Lugar de la vivienda comprada", "en", "Asturias", "Rioja(La)"],
        ["", "", "España", "(Principado de)", ""],
        ["", "España", 10.0, 6.0, ""],
        ["", "Asturias (Principado de)   ", 4.0, 3.0, "-"],
        ["", "** Datos provisionales.", "", "", ""],
        ["", "Otra", 1.0, 1.0, 1.0],
    ]
    if extra_pie:
        filas[8][1] = extra_pie
    return filas


def test_leer_cruzada_sintetica():
    df = pd.DataFrame(mivau._parsear_cruzada("2t 2026", _hoja_cruzada()))
    assert list(df.columns) == ["hoja", "anio", "trimestre", "fila_txt", "columna_txt", "valor_txt", "provisional"]
    assert len(df) == 6  # 2 filas x 3 columnas; lo posterior al pie queda fuera
    assert set(df.columna_txt) == {"en España", "Asturias (Principado de)", "Rioja(La)"}
    assert (df.anio == 2026).all() and (df.trimestre == 2).all() and df.provisional.all()
    f = df[(df.fila_txt == "Asturias (Principado de)") & (df.columna_txt == "Rioja(La)")]
    assert f.iloc[0].valor_txt == "-" and a_numero(f.iloc[0].valor_txt) is None
    vacia = df[(df.fila_txt == "España") & (df.columna_txt == "Rioja(La)")]
    assert vacia.iloc[0].valor_txt == ""


def test_leer_cruzada_sin_provisional_y_errores():
    df = pd.DataFrame(mivau._parsear_cruzada("h", _hoja_cruzada(extra_pie="Fuente: MIVAU")))
    assert not df.provisional.any()
    sin_titulo = _hoja_cruzada()
    sin_titulo[2][1] = ""
    with pytest.raises(ValueError, match="'h'"):
        mivau._parsear_cruzada("h", sin_titulo)
    with pytest.raises(ValueError, match="'h'"):
        mivau._parsear_cruzada("h", [["", "nada"]])


def test_leer_cruzada_real():
    df = mivau.leer_matriz_cruzada(FIXTURE_G0)
    assert len(df) == 78 * 19 * 19
    assert df.hoja.nunique() == 78
    assert (df.anio.min(), df.anio.max()) == (2007, 2026)
    f = df[(df.anio == 2007) & (df.trimestre == 1) & (df.fila_txt == "España") & (df.columna_txt == "en España")]
    assert a_numero(f.iloc[0].valor_txt) == 10708
    prov = df[df.provisional][["anio", "trimestre"]].drop_duplicates().values.tolist()
    assert sorted(prov) == [[2025, 3], [2026, 2]]


# --- serie vertical (boletines 09010600 y 09011600): periodos en filas, desglose en columnas sin cabecera ---

def _hoja_vertical(pie="Fuente: M. Transportes"):
    return [["", "", "", "", "", ""],
            ["", "TITULO DE LA TABLA", "", "", "", ""],
            ["", "TOTAL NACIONAL", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["", 2025.0, "", "", 100.0, 60.0],      # total anual: se ignora
            ["", "", "", "", "", ""],
            ["", 2026.0, "", "Feb", 30.0, "-"],
            ["", "", "", "Ene", 20.0, 10.0],
            ["", 2025.0, "", "Dic", 0.0, ""],
            ["", "", "", "Nov", 5.0, 4.0],
            ["", pie, "", "", "", ""]]


def test_serie_vertical_sintetica():
    df = pd.DataFrame(mivau._parsear_serie_vertical("h", _hoja_vertical()))
    assert list(df.columns) == ["hoja", "territorio_txt", "anio", "mes", "columna", "valor_txt"]
    assert set(df.territorio_txt) == {"TOTAL NACIONAL"}
    assert sorted(set(zip(df.anio, df.mes))) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]  # sin la fila anual
    v = {(r.anio, r.mes, r.columna): r.valor_txt for r in df.itertuples()}
    assert v[(2026, 2, 0)] == "30" and v[(2026, 2, 1)] == "-"
    assert v[(2025, 12, 0)] == "0" and v[(2025, 12, 1)] == ""   # 0 literal se conserva; en blanco = ""
    assert len(df) == 8


def test_serie_vertical_varios_territorios():
    filas = _hoja_vertical()[:10] + [["", "CATALUÑA", "", "", "", ""],
                                     ["", 2026.0, "", "Ene", 7.0, 3.0],
                                     ["", "Fuente: x", "", "", "", ""]]
    df = pd.DataFrame(mivau._parsear_serie_vertical("h", filas))
    assert df[df.territorio_txt == "CATALUÑA"].valor_txt.tolist() == ["7", "3"]
    assert len(df[df.territorio_txt == "TOTAL NACIONAL"]) == 8


def test_serie_vertical_errores():
    with pytest.raises(ValueError, match="mensual"):
        mivau._parsear_serie_vertical("h", [["", "TOTAL NACIONAL", ""], ["", 2025.0, 5.0]])
    sin_terr = [f for f in _hoja_vertical() if f[1] not in ("TOTAL NACIONAL", "TITULO DE LA TABLA")]
    with pytest.raises(ValueError, match="territorio"):
        mivau._parsear_serie_vertical("h", sin_terr)


def test_leer_serie_vertical_real():
    for fichero, primero in (("09011600.xls", 88254.0), ("09010600.xls", 166426.0)):
        df = mivau.leer_serie_vertical(Path(__file__).parent / "fixtures" / fichero)
        assert df.territorio_txt.unique().tolist() == ["TOTAL NACIONAL"]
        assert df.anio.min() == 1991 and (df.anio.max(), df[df.anio == 2026].mes.max()) == (2026, 6)
        assert not ((df.anio == 2025) & df.mes.isna()).any()


def test_descargar_escribe_atomico_sin_dejar_part(monkeypatch, tmp_path):
    monkeypatch.setattr(mivau.requests, "get", lambda *a, **k: _Resp(200, b"\xd0\xcf\x11\xe0datos"))
    ruta = descargar("http://x/f.xls", "D1", tmp_path)
    assert ruta.read_bytes() == b"\xd0\xcf\x11\xe0datos"
    assert [p.name for p in tmp_path.iterdir()] == [ruta.name]


@pytest.mark.parametrize("html", [b"<!DOCTYPE html><html>error</html>", b"  \n<html><body>Error</body></html>"])
def test_descargar_rechaza_html_con_200(monkeypatch, tmp_path, html):
    monkeypatch.setattr(mivau.requests, "get", lambda *a, **k: _Resp(200, html))
    with pytest.raises(RuntimeError, match="HTML"):
        descargar("http://x/f.xls", "D1", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_descargar_no_deja_archivo_si_falla_la_escritura(monkeypatch, tmp_path):
    monkeypatch.setattr(mivau.requests, "get", lambda *a, **k: _Resp(200, b"abc"))

    def _rompe(self, destino):
        raise OSError("disco lleno")
    monkeypatch.setattr(mivau.Path, "replace", _rompe)
    with pytest.raises(OSError):
        descargar("http://x/f.xls", "D1", tmp_path)
    assert list(tmp_path.iterdir()) == []
