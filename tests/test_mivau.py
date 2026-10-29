from pathlib import Path

from etl.lib.mivau import a_numero, leer_matriz, subperiodo

FIXTURE = Path(__file__).parent / "fixtures" / "31205000.xls"


def test_leer_matriz_vpo():
    df = leer_matriz(FIXTURE)
    assert list(df.columns) == ["hoja", "territorio_txt", "anio", "subperiodo_txt", "valor_txt"]
    f = df[(df.territorio_txt.str.strip() == "TOTAL NACIONAL") & (df.anio == 2008)
           & (df.subperiodo_txt == "Ene.")]
    assert len(f) == 1
    assert a_numero(f.iloc[0].valor_txt) == 4918


def test_valor_vacio_es_nulo():
    assert a_numero("-") is None
    assert a_numero("..") is None
    assert a_numero(".") is None
    assert a_numero("") is None
    assert a_numero("ND") is None
    assert a_numero("0") == 0.0
    assert a_numero("124201.8") == 124201.8


def test_columna_total_ignorada():
    df = leer_matriz(FIXTURE)
    assert not df.subperiodo_txt.str.lower().isin(["total", "media", "año"]).any()
    for txt in df.subperiodo_txt.unique():
        subperiodo(txt)  # todo subperiodo devuelto es interpretable


def test_subperiodo_trimestre():
    assert subperiodo("3º T") == ("T", 3)
    assert subperiodo("Ene.") == ("M", 1)
    assert subperiodo("1T") == ("T", 1)
    assert subperiodo("Trimestre 2") == ("T", 2)
    assert subperiodo("IV") == ("T", 4)
    assert subperiodo("2º") == ("T", 2)
    assert subperiodo("Sept.") == ("M", 9)
    for malo in ("Total", "Media", "Año", "Mario", "(trimestre)"):
        try:
            subperiodo(malo)
        except ValueError:
            continue
        raise AssertionError(malo)
