"""Validación de tablas contra Campos y el maestro, y cuadre jerárquico."""
import re

import pandas as pd

_ERRORES_EXCEL = {"#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"}
_RE_LONG = re.compile(r"^(?:VAR)?CHAR\((\d+)\)$", re.I)
_RE_ENUM = re.compile(r"^ENUM\((.*)\)$", re.I | re.S)
_RE_DECIMAL = re.compile(r"^DECIMAL\((\d+)\s*,\s*(\d+)\)$", re.I)


def escala_decimal(tipo: str) -> int | None:
    """Escala s de un `DECIMAL(p,s)`; None si el tipo no es DECIMAL."""
    m = _RE_DECIMAL.match(str(tipo).strip())
    return int(m.group(2)) if m else None


def _es_nulo(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v == ""
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _muestra(df: pd.DataFrame, mascara: pd.Series, n: int = 3) -> str:
    return ", ".join(map(str, df.index[mascara][:n].tolist()))


def validar_tabla(df: pd.DataFrame, campos: pd.DataFrame, maestro: pd.DataFrame) -> list[str]:
    """Devuelve la lista de errores en texto; vacía si la tabla es válida."""
    errores: list[str] = []
    esperadas = list(campos["campo"])
    if list(df.columns) != esperadas:
        errores.append(f"columnas distintas de Campos: tabla={list(df.columns)} esperadas={esperadas}")

    if "id_registro" in df.columns:
        dup = df["id_registro"][df["id_registro"].duplicated(keep=False)]
        if len(dup):
            ejemplos = ", ".join(map(str, dup.unique()[:5]))
            errores.append(f"id_registro duplicado: {dup.nunique()} valores (p. ej. {ejemplos})")

    for col in df.columns:
        serie = df[col]
        if serie.dtype != object and not pd.api.types.is_string_dtype(serie):
            continue
        m = serie.map(lambda v: isinstance(v, str) and v.strip() in _ERRORES_EXCEL)
        if m.any():
            valores = ", ".join(sorted(set(serie[m].str.strip())))
            errores.append(f"celda de error de Excel en columna '{col}': {valores} "
                           f"(filas {_muestra(df, m)})")

    if "cod_territorio" in df.columns:
        validos = set(maestro["cod_territorio"].dropna())
        malos = sorted({str(v) for v in df["cod_territorio"].dropna()} - {str(x) for x in validos})
        if malos:
            errores.append(f"cod_territorio no está en el maestro: {', '.join(malos[:10])}")

    for _, c in campos.iterrows():
        col, tipo = c["campo"], str(c["tipo_mysql"]).strip()
        if col not in df.columns:
            continue
        serie = df[col]
        nulos = serie.map(_es_nulo)
        if str(c["nulo"]).strip().upper() == "NO" and nulos.any():
            errores.append(f"valores nulos en columna '{col}' (nulo=NO): "
                           f"{int(nulos.sum())} filas (p. ej. {_muestra(df, nulos)})")
        m_long = _RE_LONG.match(tipo)
        if m_long:
            maximo = int(m_long.group(1))
            largo = serie.map(lambda v: len(str(v)) if not _es_nulo(v) else 0)
            exc = largo > maximo
            if exc.any():
                errores.append(f"longitud excedida en columna '{col}' (máx {maximo}): "
                               f"{int(exc.sum())} filas (p. ej. {_muestra(df, exc)})")
        escala = escala_decimal(tipo)
        if escala is not None:
            num = pd.to_numeric(serie, errors="coerce").astype("float64")
            largos = num.notna() & (num.round(escala) != num)
            if largos.any():
                errores.append(f"más decimales que la escala de {tipo} en columna '{col}': "
                               f"{int(largos.sum())} filas (p. ej. {_muestra(df, largos)}: {num[largos].iloc[0]!r})")
        m_enum = _RE_ENUM.match(tipo)
        if m_enum:
            permitidos = set(re.findall(r"'((?:[^']|'')*)'", m_enum.group(1)))
            permitidos = {p.replace("''", "'") for p in permitidos}
            fuera = serie.map(lambda v: not _es_nulo(v) and str(v) not in permitidos)
            if fuera.any():
                vals = ", ".join(sorted({str(v) for v in serie[fuera]})[:5])
                errores.append(f"valor fuera de ENUM en columna '{col}': {vals}")
    return errores


def cuadre_jerarquico(df: pd.DataFrame, medida: str, dimensiones: list[str]) -> pd.DataFrame:
    """Nacional vs suma de CCAA y cada CCAA vs suma de sus provincias. Solo informa."""
    claves = ["periodo"] + list(dimensiones)
    columnas = ["nivel_padre", "cod_padre"] + claves + ["valor_padre", "suma_hijos", "diferencia"]
    d = df.copy()
    d[medida] = pd.to_numeric(d[medida], errors="coerce").fillna(0.0)
    resultado = []

    def comparar(padres: pd.DataFrame, hijos: pd.DataFrame, nivel_padre: str, por: list[str]):
        if padres.empty or hijos.empty:
            return
        suma = hijos.groupby(por + claves, dropna=False)[medida].sum().rename("suma_hijos").reset_index()
        union = padres.merge(suma, on=por + claves, how="inner")
        for _, f in union.iterrows():
            dif = float(f[medida]) - float(f["suma_hijos"])
            if abs(dif) > 1e-6:
                resultado.append({"nivel_padre": nivel_padre, "cod_padre": f["cod_territorio"],
                                  **{k: f[k] for k in claves}, "valor_padre": float(f[medida]),
                                  "suma_hijos": float(f["suma_hijos"]), "diferencia": dif})

    nac = d[d["nivel"] == "Nacional"]
    ccaa = d[d["nivel"] == "CCAA"]
    prov = d[d["nivel"] == "Provincia"]
    comparar(nac, ccaa, "Nacional", [])
    comparar(ccaa, prov, "CCAA", ["cod_ccaa"])
    return pd.DataFrame(resultado, columns=columnas)
