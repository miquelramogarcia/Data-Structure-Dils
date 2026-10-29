from datetime import date

import pandas as pd

from etl.lib.modelo import (COLUMNAS_CONTROL, COLUMNAS_TERRITORIO, COLUMNAS_TIEMPO,
                            construir_tabla)
from etl.lib.periodos import periodo_mensual
from etl.lib.validar import cuadre_jerarquico, validar_tabla

TERR = {
    "ES": dict(nivel="Nacional", cod_territorio="ES", cod_ccaa=None, nombre_ccaa=None,
               cod_provincia=None, nombre_provincia=None, cod_municipio=None, nombre_municipio=None),
    "CA01": dict(nivel="CCAA", cod_territorio="CA01", cod_ccaa="01", nombre_ccaa="Andalucía",
                 cod_provincia=None, nombre_provincia=None, cod_municipio=None, nombre_municipio=None),
    "PR04": dict(nivel="Provincia", cod_territorio="PR04", cod_ccaa="01", nombre_ccaa="Andalucía",
                 cod_provincia="04", nombre_provincia="Almería", cod_municipio=None, nombre_municipio=None),
    "PR11": dict(nivel="Provincia", cod_territorio="PR11", cod_ccaa="01", nombre_ccaa="Andalucía",
                 cod_provincia="11", nombre_provincia="Cádiz", cod_municipio=None, nombre_municipio=None),
}


def _maestro():
    filas = []
    for t in TERR.values():
        f = dict(t, alias=t["cod_territorio"], nombre_territorio=t["cod_territorio"],
                 fuente_alias=None, cod_fuente_alias=None)
        filas.append(f)
    return pd.DataFrame(filas)


def _fila(cod, valor, regimen="TOTAL", mes=6, **extra):
    return {**TERR[cod], "regimen": regimen, **periodo_mensual(2026, mes), "valor": valor, **extra}


def _tabla(filas):
    return construir_tabla(pd.DataFrame(filas), ["regimen"], ["valor"], date(2026, 7, 1))


def _campos():
    cols = [("id_registro", "VARCHAR(64)", "NO"),
            ("nivel", "ENUM('Nacional','CCAA','Provincia','Municipio')", "NO"),
            ("cod_territorio", "VARCHAR(7)", "NO"),
            ("cod_ccaa", "CHAR(2)", "SÍ"), ("nombre_ccaa", "VARCHAR(64)", "SÍ"),
            ("cod_provincia", "CHAR(2)", "SÍ"), ("nombre_provincia", "VARCHAR(64)", "SÍ"),
            ("cod_municipio", "CHAR(5)", "SÍ"), ("nombre_municipio", "VARCHAR(64)", "SÍ"),
            ("regimen", "VARCHAR(16)", "NO"),
            ("periodo", "VARCHAR(7)", "NO"), ("frecuencia", "CHAR(1)", "NO"),
            ("anio", "SMALLINT UNSIGNED", "NO"), ("trimestre", "TINYINT", "SÍ"),
            ("mes", "TINYINT", "SÍ"), ("fecha", "DATE", "NO"),
            ("valor", "DECIMAL(12,2)", "SI"),
            ("provisional", "TINYINT(1)", "NO"), ("fecha_descarga", "DATE", "NO")]
    return pd.DataFrame([dict(tabla="t", campo=c, tipo_mysql=t, nulo=n, clave="", descripcion="", ejemplo="")
                         for c, t, n in cols])


def test_id_registro():
    df = _tabla([_fila("PR04", 1.0)])
    assert df.loc[0, "id_registro"] == "PR04_TOTAL_2026M06"


def test_orden_columnas():
    df = _tabla([_fila("PR04", 1.0)])
    esperado = (["id_registro"] + COLUMNAS_TERRITORIO + ["regimen"] + COLUMNAS_TIEMPO
                + ["valor"] + COLUMNAS_CONTROL)
    assert list(df.columns) == esperado
    assert COLUMNAS_TIEMPO == ["periodo", "frecuencia", "anio", "trimestre", "mes", "fecha"]
    assert (df["provisional"] == 0).all()
    assert df.loc[0, "fecha_descarga"] == date(2026, 7, 1)


def test_validar_tabla_correcta():
    df = _tabla([_fila("PR04", 1.0), _fila("PR11", 2.0)])
    assert validar_tabla(df, _campos(), _maestro()) == []


def test_validar_detecta_duplicado():
    df = _tabla([_fila("PR04", 1.0), _fila("PR04", 2.0)])
    errs = validar_tabla(df, _campos(), _maestro())
    assert any("duplicado" in e and "PR04_TOTAL_2026M06" in e for e in errs)


def test_validar_detecta_territorio_inexistente():
    df = _tabla([_fila("PR04", 1.0)])
    df.loc[0, "cod_territorio"] = "PR99"
    errs = validar_tabla(df, _campos(), _maestro())
    assert any("PR99" in e for e in errs)


def test_validar_detecta_error_excel():
    df = _tabla([_fila("PR04", 1.0)])
    df["valor"] = df["valor"].astype(object)
    df.loc[0, "valor"] = "#REF!"
    errs = validar_tabla(df, _campos(), _maestro())
    assert any("#REF!" in e and "valor" in e for e in errs)


def test_validar_nulos_longitud_enum_columnas():
    df = _tabla([_fila("PR04", 1.0)])
    df.loc[0, "regimen"] = ""
    df.loc[0, "nombre_provincia"] = "x" * 65
    df.loc[0, "nivel"] = "Barrio"
    errs = validar_tabla(df, _campos(), _maestro())
    assert any("regimen" in e and "nulo" in e for e in errs)
    assert any("nombre_provincia" in e and "longitud" in e for e in errs)
    assert any("nivel" in e and "ENUM" in e for e in errs)
    errs = validar_tabla(df[["nivel", "id_registro"]], _campos(), _maestro())
    assert any("columnas" in e for e in errs)


def test_cuadre_detecta_descuadre():
    df = _tabla([_fila("ES", 10.0), _fila("CA01", 10.0), _fila("PR04", 4.0), _fila("PR11", 5.0)])
    r = cuadre_jerarquico(df, "valor", ["regimen"])
    assert list(r.columns) == ["nivel_padre", "cod_padre", "periodo", "regimen",
                               "valor_padre", "suma_hijos", "diferencia"]
    assert len(r) == 1
    assert r.iloc[0]["cod_padre"] == "CA01" and abs(r.iloc[0]["diferencia"] - 1.0) < 1e-9


def test_cuadre_ok_vacio():
    df = _tabla([_fila("ES", 10.0), _fila("CA01", 10.0), _fila("PR04", 4.0), _fila("PR11", 6.0)])
    assert cuadre_jerarquico(df, "valor", ["regimen"]).empty


def test_columnas_territorio_extra_van_tras_el_municipio():
    # SERPAVI: cod_distrito y cod_seccion tras nombre_municipio y antes de las dimensiones; no entran en la clave
    df = pd.DataFrame([_fila("PR04", 1, cod_distrito="0401301", cod_seccion=None)])
    t = construir_tabla(df, ["regimen"], ["valor"], date(2026, 7, 1), territorio_extra=["cod_distrito", "cod_seccion"])
    assert list(t.columns) == (["id_registro"] + COLUMNAS_TERRITORIO + ["cod_distrito", "cod_seccion", "regimen"]
                               + COLUMNAS_TIEMPO + ["valor"] + COLUMNAS_CONTROL)
    assert t["id_registro"].iloc[0] == "PR04_TOTAL_2026M06"
