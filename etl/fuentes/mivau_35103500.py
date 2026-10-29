"""MIVAU-35103500: valor tasado medio de la vivienda libre en municipios de más de 25.000 habitantes.

Tabla `mivau_valor_tasado_municipios_25000` (nivel Municipio). Euros por m2 y número de tasaciones, por
municipio, antigüedad y trimestre. El boletín trae UNA HOJA POR TRIMESTRE ("T1A2005" ... "T2A2026"), con
columnas Provincia, Municipio y los valores. Dos formatos:
- 2005T1-2009T4: "Valor medio / Total" y "Tasaciones / Total" (solo antigüedad TOTAL).
- 2010T1 en adelante: "Valor tasado de vivienda" y "Número de tasaciones", cada una con "Hasta cinco años
  de antigüedad", "Con más de cinco años de antigüedad" y "Total".
Las columnas se localizan por el texto de las cabeceras, no por posición.

La provincia aparece solo en la primera fila de cada grupo; las siguientes la heredan. En las hojas desde
2020T1 el boletín añade municipios ordenados alfabéticamente DENTRO de su provincia pero antes de la fila
que lleva la etiqueta (p. ej. "Almuñecar", de Granada, va tras Puente Génil y antes de la fila "Granada").
Esos siete casos conocidos están en `PROVINCIA_REAL`: su provincia real se impone siempre (con aviso). Cualquier
otro municipio que no exista en su provincia heredada hace fallar el proceso, con la hoja y el nombre.
Valores medios: `CUADRE = False`.
"""
import re
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import xlrd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, tabla_final, url_dataset
from etl.lib.periodos import periodo_trimestral
from etl.lib.territorios import TerritorioDesconocido, cargar_maestro, normalizar, resolver_municipio

DATASET_ID = "MIVAU-35103500"
TABLA = "mivau_valor_tasado_municipios_25000"
DIMENSIONES = ["antiguedad"]
MEDIDA = "valor_tasado_eur_m2"
TASACIONES = "num_tasaciones"
MEDIDAS = [MEDIDA, TASACIONES]
CUADRE = False
# Municipios que el boletín (desde 2020T1) coloca bajo la etiqueta de la provincia anterior: etiqueta del
# boletín -> provincia real (nombre del maestro). Lista cerrada: un caso nuevo debe revisarse y añadirse aquí.
PROVINCIA_REAL = {"Almuñecar": "Granada", "Azuqueca de Henares": "Guadalajara", "Illescas": "Toledo",
                  "Ames": "La Coruña", "Cangas": "Pontevedra", "Almazora/Almassora": "Castellón/Castelló",
                  "Benicarló": "Castellón/Castelló"}

_RE_HOJA = re.compile(r"^T([1-4])A((?:19|20)\d{2})$")
_ANTIGUEDAD = (("total", "TOTAL"), ("hasta cinco", "HASTA_5_ANOS"), ("con mas de cinco", "MAS_5_ANOS"))


def _texto(celda) -> str:
    return " ".join(str(celda).split())


def _periodo_hoja(nombre: str, filas: list[list]) -> tuple[int, int]:
    """(año, trimestre) del nombre de la hoja, comprobado contra el título ("Primer trimestre de 2005")."""
    m = _RE_HOJA.match(nombre.strip())
    if not m:
        raise ValueError(f"{DATASET_ID}: nombre de hoja no reconocido {nombre!r} (se espera T1A2005)")
    trim, anio = int(m.group(1)), int(m.group(2))
    for fila in filas[:20]:
        t = mivau._RE_TITULO_TRIM.search(normalizar(" ".join(_texto(c) for c in fila)))
        if t:
            esperado = (mivau._ORDINALES[t.group(1)], int(t.group(2)))
            if esperado != (trim, anio):
                raise ValueError(f"{DATASET_ID}: la hoja {nombre!r} dice {esperado} en su título")
            break
    return anio, trim


def _columnas(filas: list[list], hdr: int) -> dict[int, tuple[str, str]]:
    """{columna: (medida, antigüedad)} a partir de las cabeceras (fila `hdr` = la de "Provincia")."""
    grupo, resultado = None, {}
    for c in range(3, len(filas[hdr])):
        g = normalizar(filas[hdr][c])
        if g:
            grupo = g
        sub = normalizar(filas[hdr + 1][c])
        if not sub:
            continue
        if grupo is None:
            raise ValueError(f"{DATASET_ID}: columna {c} sin cabecera de grupo")
        if grupo.startswith("valor"):
            medida = MEDIDA
        elif "tasaciones" in grupo:
            medida = TASACIONES
        else:
            raise ValueError(f"{DATASET_ID}: grupo de columnas no reconocido {grupo!r}")
        ant = next((v for k, v in _ANTIGUEDAD if sub.startswith(k)), None)
        if ant is None:
            raise ValueError(f"{DATASET_ID}: antigüedad no reconocida {filas[hdr + 1][c]!r}")
        resultado[c] = (medida, ant)
    if not resultado:
        raise ValueError(f"{DATASET_ID}: no se encontraron columnas de valores")
    return resultado


def _hoja_a_filas(nombre: str, filas: list[list]) -> list[dict]:
    anio, trim = _periodo_hoja(nombre, filas)
    hdr = next((r for r, f in enumerate(filas) if _texto(f[1]) == "Provincia"), None)
    if hdr is None:
        raise ValueError(f"{DATASET_ID}: hoja {nombre!r} sin cabecera 'Provincia'")
    cols = _columnas(filas, hdr)
    municipios, provincia = [], None
    for r in range(hdr + 2, len(filas)):
        f = filas[r]
        prov, mun = _texto(f[1]), _texto(f[2])
        if prov and not mun:
            break  # nota al pie ("n.r: el dato no es representativo...")
        if not mun or normalizar(mun).startswith("de antiguedad"):
            continue
        provincia = prov or provincia
        if provincia is None:
            raise ValueError(f"{DATASET_ID}: hoja {nombre!r}: municipio {mun!r} sin provincia")
        municipios.append({"provincia": provincia, "municipio": mun, "fila": f})
    out = []
    for m in municipios:
        celdas = {c: m["fila"][c] for c in cols}
        if all(_texto(v) == "" for v in celdas.values()):
            continue
        for ant in sorted({a for _, a in cols.values()}):
            fila = {"anio": anio, "trimestre": trim, "hoja": nombre, "provincia": m["provincia"],
                    "municipio": m["municipio"], "antiguedad": ant}
            for c, (medida, a) in cols.items():
                if a == ant:
                    fila[medida] = mivau.a_numero(celdas[c])
            out.append(fila)
    if not out:
        raise ValueError(f"{DATASET_ID}: hoja {nombre!r} sin filas con datos")
    return out


def leer_municipios(path: Path) -> pd.DataFrame:
    """Boletín → filas largas: anio, trimestre, hoja, provincia, municipio, antiguedad, medidas."""
    wb = xlrd.open_workbook(str(path))
    filas = []
    for nombre in wb.sheet_names():
        hoja = wb.sheet_by_name(nombre)
        matriz = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
        filas += _hoja_a_filas(nombre, matriz)
    df = pd.DataFrame(filas)
    for m in MEDIDAS:
        df[m] = pd.to_numeric(df[m], errors="coerce")
    return df


def _resolver(maestro: pd.DataFrame, provincia: str, municipio: str, hoja: str = "?"):
    """(territorio, provincia usada). Los de PROVINCIA_REAL usan su provincia real; el resto, la heredada."""
    real = PROVINCIA_REAL.get(municipio)
    usada = real or provincia
    try:
        return resolver_municipio(maestro, municipio, usada), usada
    except TerritorioDesconocido as e:
        raise TerritorioDesconocido(f"{DATASET_ID}, hoja {hoja.strip()!r}: {e}") from None


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve cada municipio con su provincia y valida la tabla."""
    maestro = cargar_maestro(LIBRO)
    largo = leer_municipios(path)
    claves = largo[["provincia", "municipio", "hoja"]].drop_duplicates(["provincia", "municipio"])
    territorios, corregidos = {}, set()
    for k in claves.itertuples(index=False):
        territorio, usada = _resolver(maestro, k.provincia, k.municipio, k.hoja)
        territorios[(k.provincia, k.municipio)] = territorio
        if usada != k.provincia:
            corregidos.add(f"{k.municipio!r}: etiqueta heredada {k.provincia!r}, es de {usada!r}")
    if corregidos:
        warnings.warn(f"{DATASET_ID}: municipios cuya provincia heredada no es la suya: "
                      + "; ".join(sorted(corregidos)), stacklevel=2)
    filas = []
    for r in largo.itertuples(index=False):
        t = territorios[(r.provincia, r.municipio)]
        filas.append({**t, "antiguedad": r.antiguedad, **periodo_trimestral(int(r.anio), int(r.trimestre)),
                      MEDIDA: getattr(r, MEDIDA), TASACIONES: getattr(r, TASACIONES), "provisional": 0})
    return tabla_final(pd.DataFrame(filas), DATASET_ID, TABLA, DIMENSIONES, MEDIDA, maestro,
                       fecha_descarga, entero=False, medidas_enteras=[TASACIONES])


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
