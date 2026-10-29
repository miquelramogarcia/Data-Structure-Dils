"""Descarga y lectura de los boletines estadísticos del MIVAU (matrices .xls con cabeceras de año y subperiodo)."""
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import xlrd

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")
_MESES_VALIDOS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
                  "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
                  "diciembre": 12, "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
                  "jul": 7, "ago": 8, "agos": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11,
                  "dic": 12}
_ROMANOS = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
_NULOS = {"", "-", "..", "."}
_RE_ANIO = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_RE_MARCA = re.compile(r"\s*\(\s*(?:\*+|p)\s*\)\s*$", re.IGNORECASE)
_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4}
_RE_TITULO_TRIM = re.compile(r"(primer|primero|segundo|tercer|tercero|cuarto)\s+trimestre\s+de\s+((?:19|20)\d{2})")
_RE_TRIM = re.compile(r"^(?:(?P<a>[1-4])\s*[oa]?\s*(?:t|trim|trimestre)?|(?:t|trim|trimestre)\s*(?P<b>[1-4]))$")


def descargar(url: str, dataset_id: str, destino: Path = Path("etl/descargas")) -> Path:
    """Descarga `url` a `<dataset_id>_<AAAAMMDD>.<ext>`; si el de hoy ya existe, no se repite."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix.lstrip(".").lower() or "xls"
    ruta = destino / f"{dataset_id}_{date.today():%Y%m%d}.{ext}"
    if ruta.exists():
        return ruta
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Descarga fallida ({r.status_code}): {url}")
    if r.content.lstrip()[:1] == b"<":  # página de error HTML servida con 200 (el .xls/.xlsx nunca empieza por "<")
        raise RuntimeError(f"La descarga devolvió una página HTML, no un archivo de datos: {url}")
    parcial = ruta.with_name(ruta.name + ".part")
    try:
        parcial.write_bytes(r.content)
        parcial.replace(ruta)  # atómico: nunca queda un archivo a medias con el nombre definitivo
    finally:
        parcial.unlink(missing_ok=True)
    return ruta


def a_numero(valor_txt) -> float | None:
    """Convierte el texto de una celda en número; '-', '..', '.', vacío o texto dan None."""
    if valor_txt is None:
        return None
    if isinstance(valor_txt, (int, float)) and not isinstance(valor_txt, bool):
        return float(valor_txt)
    t = str(valor_txt).strip()
    if t in _NULOS:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _norm(txt) -> str:
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split()).rstrip(".").strip()


def marca_provisional(txt) -> bool:
    """True si la cabecera lleva una marca de dato provisional al final: '2º (**)', 'Ene. (*)', 'Ene. (p)'."""
    return bool(_RE_MARCA.search(str(txt)))


def subperiodo(txt: str) -> tuple[str, int]:
    """('M', mes) o ('T', trimestre) a partir de 'Ene.', '1T', '3º T', 'Trimestre 1', 'I'-'IV'.

    Una marca final de provisional ('2º (**)') se ignora aquí; `marca_provisional` la detecta.
    """
    t = _norm(_RE_MARCA.sub("", str(txt)))
    if t in _MESES_VALIDOS:
        return ("M", _MESES_VALIDOS[t])
    m = _RE_TRIM.match(t)
    if m:
        return ("T", int(m.group("a") or m.group("b")))
    base = re.sub(r"\s*(t|trim|trimestre)$", "", t)
    if base in _ROMANOS:
        return ("T", _ROMANOS[base])
    raise ValueError(f"Subperiodo no reconocido: {txt!r}")


def _es_subperiodo(celda) -> bool:
    if celda is None or celda == "":
        return False
    try:
        subperiodo(celda)
        return True
    except ValueError:
        return False


def _anio_de(celda) -> int | None:
    if isinstance(celda, float) and celda == int(celda):
        celda = int(celda)
    t = str(celda).strip()
    if not t or len(t) > 25:
        return None
    m = _RE_ANIO.search(t)
    return int(m.group()) if m else None


def _texto_valor(celda) -> str:
    if isinstance(celda, float):
        return str(int(celda)) if celda == int(celda) else repr(celda)
    return str(celda).strip()


def _en_blanco(celda) -> bool:
    return celda == "" or (isinstance(celda, str) and not celda.strip())


class SinCabecera(ValueError):
    """La hoja no tiene bloque de cabeceras (año + subperiodo)."""


_RE_PIE = re.compile(r"^\s*(fuente|nota|notas|nd\s*-|\(|\*)", re.IGNORECASE)


def _es_pie(texto: str) -> bool:
    t = texto.strip()
    return bool(_RE_PIE.match(t)) or (len(t) > 60 and t.endswith("."))


def _parsear_valores(nombre: str, filas: list[list]) -> list[dict]:
    """Convierte la matriz 2-D de una hoja en filas largas (hoja, territorio_txt, anio, subperiodo_txt, valor_txt).

    Cabeceras: fila del año (regex 19xx/20xx, arrastrada a la derecha) y, en las 3 filas siguientes, la
    primera con >= 2 subperiodos válidos. Las columnas cuyo subperiodo no es mes/trimestre (Total, Media,
    Año...) se ignoran. La columna del territorio es la anterior a la primera columna de periodo.

    Fila de territorio: tras las cabeceras y antes de la primera línea de pie (empieza por Fuente, Nota,
    "(", "*" o "ND-", o es una frase larga acabada en "."), con texto en la columna del territorio y al
    menos una celda no vacía (número, '-', '..' o texto) en las columnas activas. Columna activa: tiene
    algún valor no vacío en alguna fila de territorio; las de relleno (meses futuros) se saltan. Para cada
    fila se emite una fila por columna activa: la celda vacía da valor_txt "" y el texto ("ND", "(p)")
    pasa tal cual; a_numero los convierte en None.
    """
    for r, fila in enumerate(filas[:40]):
        if not any(_anio_de(c) for c in fila):
            continue
        rs = next((x for x in range(r + 1, min(r + 4, len(filas)))
                   if sum(_es_subperiodo(c) for c in filas[x]) >= 2), None)
        if rs is not None:
            break
    else:
        raise SinCabecera(f"Hoja {nombre!r}: no se encuentra la cabecera de año/subperiodo")
    anios, actual = [], None
    for c in fila:
        actual = _anio_de(c) or actual
        anios.append(actual)
    cols = [(c, anios[c], str(filas[rs][c]).strip()) for c in range(len(filas[rs]))
            if anios[c] and _es_subperiodo(filas[rs][c])]
    col_terr = cols[0][0] - 1
    if col_terr < 0:
        raise ValueError(f"Hoja {nombre!r}: no hay columna de territorio a la izquierda de los periodos")
    candidatas = []
    for fila_d in filas[rs + 1:]:
        terr = fila_d[col_terr]
        if isinstance(terr, str) and terr.strip():
            if _es_pie(terr):
                break
            candidatas.append((terr.strip(), fila_d))
    activas = [(c, a, s) for c, a, s in cols if any(not _en_blanco(f[c]) for _, f in candidatas)]
    out = []
    for terr, fila_d in candidatas:
        if all(_en_blanco(fila_d[c]) for c, _, _ in activas):
            continue
        out += [{"hoja": nombre, "territorio_txt": terr, "anio": a, "subperiodo_txt": s,
                 "valor_txt": "" if _en_blanco(fila_d[c]) else _texto_valor(fila_d[c])}
                for c, a, s in activas]
    if not out:
        raise ValueError(f"Hoja {nombre!r}: no se encuentran filas de territorio con datos")
    return out


def leer_matriz(path: Path, hojas: list[str] | None = None) -> pd.DataFrame:
    """Lee un boletín MIVAU y devuelve formato largo: hoja, territorio_txt, anio, subperiodo_txt, valor_txt.

    Con `hojas`, cada nombre debe existir y tener cabeceras (ValueError con el nombre de la hoja si no).
    Sin `hojas`, se saltan las hojas sin cabecera, pero se exige al menos una con datos.
    """
    wb = xlrd.open_workbook(str(path))
    existentes = wb.sheet_names()
    if hojas is not None:
        faltan = [h for h in hojas if h not in existentes]
        if faltan:
            raise ValueError(f"Hojas no encontradas en {Path(path).name}: {faltan}; hay {existentes}")
    filas = []
    for nombre in existentes:
        if hojas is not None and nombre not in hojas:
            continue
        hoja = wb.sheet_by_name(nombre)
        matriz = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
        try:
            filas += _parsear_valores(nombre, matriz)
        except SinCabecera:
            if hojas is not None:
                raise
    if not filas:
        raise ValueError(f"{Path(path).name}: ninguna hoja con cabeceras y datos")
    return pd.DataFrame(filas, columns=["hoja", "territorio_txt", "anio", "subperiodo_txt", "valor_txt"])


def _parsear_cruzada(nombre: str, filas: list[list]) -> list[dict]:
    """Hoja con una matriz cruzada de un solo periodo: filas = lugar de la vivienda, columnas = residencia del comprador.

    Layout (boletín 340101g0): el periodo está en una celda de las primeras filas ("Primer trimestre de
    2007", con "(**)" delante si es provisional); la cabecera empieza en la fila cuya celda dice "Lugar de
    la vivienda comprada" y ocupa esa fila y la siguiente (los rótulos se parten en dos líneas y se
    unen con un espacio); los datos siguen hasta la primera línea de pie. La hoja es provisional si ese
    pie menciona "provisional". Celda vacía → valor_txt "" y texto tal cual (a_numero los pasa a None).
    Devuelve filas largas: hoja, anio, trimestre, fila_txt, columna_txt, valor_txt, provisional.
    """
    periodo = None
    for fila in filas[:15]:
        for c in fila:
            m = _RE_TITULO_TRIM.search(_norm(c)) if isinstance(c, str) else None
            if m:
                periodo = (int(m.group(2)), _ORDINALES[m.group(1)])
                break
        if periodo:
            break
    if periodo is None:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra el título con el trimestre y el año")
    cab = col_fila = None
    for r, fila in enumerate(filas[:30]):
        for c, v in enumerate(fila):
            if isinstance(v, str) and _norm(v).startswith("lugar de la vivienda"):
                cab, col_fila = r, c
                break
        if cab is not None:
            break
    if cab is None or cab + 2 >= len(filas):
        raise ValueError(f"Hoja {nombre!r}: no se encuentra la cabecera 'Lugar de la vivienda comprada'")
    columnas = []
    for c in range(col_fila + 1, len(filas[cab])):
        rotulo = " ".join(" ".join(str(filas[x][c]).split()) for x in (cab, cab + 1) if str(filas[x][c]).strip())
        if rotulo:
            columnas.append((c, rotulo))
    out, provisional = [], False
    for fila in filas[cab + 2:]:
        etiqueta = fila[col_fila]
        if not (isinstance(etiqueta, str) and etiqueta.strip()):
            continue
        if _es_pie(etiqueta):
            provisional = "provisional" in _norm(etiqueta)
            break
        out += [{"hoja": nombre, "anio": periodo[0], "trimestre": periodo[1],
                 "fila_txt": " ".join(etiqueta.split()), "columna_txt": rotulo,
                 "valor_txt": "" if _en_blanco(fila[c]) else _texto_valor(fila[c])}
                for c, rotulo in columnas]
    if not out:
        raise ValueError(f"Hoja {nombre!r}: no se encuentran filas de datos")
    for f in out:
        f["provisional"] = provisional
    return out


def leer_matriz_cruzada(path: Path) -> pd.DataFrame:
    """Lee un boletín MIVAU con una hoja por trimestre y matriz vivienda × comprador (340101g0).

    Devuelve formato largo: hoja, anio, trimestre, fila_txt, columna_txt, valor_txt, provisional.
    Todas las hojas deben tener la estructura (ValueError con el nombre de la hoja si no).
    """
    wb = xlrd.open_workbook(str(path))
    filas = []
    for hoja in wb.sheets():
        matriz = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
        filas += _parsear_cruzada(hoja.name.strip(), matriz)
    return pd.DataFrame(filas, columns=["hoja", "anio", "trimestre", "fila_txt", "columna_txt",
                                        "valor_txt", "provisional"])


def _parsear_hoja_trimestre(nombre: str, filas: list[list]) -> list[dict]:
    """Hoja de un solo trimestre con territorios en filas y varias columnas de desglose (boletín 34020180).

    Layout: el periodo está en una celda de las primeras filas ("Primer trimestre de 2019", con "(**)" delante
    si es provisional); la cabecera es la fila cuya primera celda con texto dice "TOTAL" (las demás celdas de
    esa fila son los rótulos de columna); la columna del territorio es la que contiene "TOTAL NACIONAL"; los
    datos siguen hasta la primera línea de pie. La hoja es provisional si ese pie menciona "provisional".
    Devuelve filas largas: hoja, anio, trimestre, territorio_txt, columna_txt, valor_txt, provisional.
    """
    periodo = None
    for fila in filas[:15]:
        for c in fila:
            m = _RE_TITULO_TRIM.search(_norm(c)) if isinstance(c, str) else None
            if m:
                periodo = (int(m.group(2)), _ORDINALES[m.group(1)])
                break
        if periodo:
            break
    if periodo is None:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra el título con el trimestre y el año")
    cab = None
    for r, fila in enumerate(filas[:30]):
        textos = [c for c in fila if isinstance(c, str) and c.strip()]
        if textos and _norm(textos[0]) == "total":
            cab = r
            break
    if cab is None:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra la fila de cabecera que empieza por 'TOTAL'")
    columnas = [(c, " ".join(str(v).split())) for c, v in enumerate(filas[cab]) if str(v).strip()]
    col_terr = next((c for fila in filas[cab + 1:cab + 4] for c, v in enumerate(fila)
                     if isinstance(v, str) and _norm(v) == "total nacional"), None)
    if col_terr is None:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra la fila 'TOTAL NACIONAL'")
    out, provisional = [], False
    for fila in filas[cab + 1:]:
        etiqueta = fila[col_terr]
        if not (isinstance(etiqueta, str) and etiqueta.strip()):
            continue
        if _es_pie(etiqueta):
            provisional = "provisional" in _norm(etiqueta)
            break
        out += [{"hoja": nombre, "anio": periodo[0], "trimestre": periodo[1],
                 "territorio_txt": " ".join(etiqueta.split()), "columna_txt": rotulo,
                 "valor_txt": "" if _en_blanco(fila[c]) else _texto_valor(fila[c])}
                for c, rotulo in columnas]
    if not out:
        raise ValueError(f"Hoja {nombre!r}: no se encuentran filas de datos")
    for f in out:
        f["provisional"] = provisional
    return out


def leer_hojas_trimestre(path: Path) -> pd.DataFrame:
    """Lee un boletín MIVAU con una hoja por trimestre, territorios en filas y columnas de desglose (34020180).

    Devuelve formato largo: hoja, anio, trimestre, territorio_txt, columna_txt, valor_txt, provisional.
    Todas las hojas deben tener la estructura (ValueError con el nombre de la hoja si no).
    """
    wb = xlrd.open_workbook(str(path))
    filas = []
    for hoja in wb.sheets():
        matriz = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
        filas += _parsear_hoja_trimestre(hoja.name.strip(), matriz)
    return pd.DataFrame(filas, columns=["hoja", "anio", "trimestre", "territorio_txt", "columna_txt",
                                        "valor_txt", "provisional"])


def _parsear_serie_vertical(nombre: str, filas: list[list]) -> list[dict]:
    """Hoja con los periodos en filas y el desglose en columnas SIN cabecera de texto (boletines 09010600 y 09011600).

    Layout: una línea con solo el nombre del territorio ("TOTAL NACIONAL"); debajo, filas anuales (año sin
    mes) y bloques mensuales (el año solo aparece en la primera fila del bloque, los meses siguen en filas
    sucesivas). La columna de los meses es la que tiene >= 2 meses ("Ene", "Feb"...); la del año es la
    columna con más años a su izquierda; los valores empiezan en la columna siguiente a la de los meses.
    Las filas anuales se ignoran (son suma o media de los meses). Los rótulos de las columnas de valores
    son una imagen incrustada en el .xls, no texto: se devuelve el índice de columna (0 = primera columna
    de valores) y quien llama lo asocia a su significado. Se emiten TODAS las columnas hasta la última de
    la hoja (celda en blanco → valor_txt ""), para que quien llama pueda comprobar las no mapeadas.
    Un pie ("Fuente...") corta la hoja. Devuelve filas largas: hoja, territorio_txt, anio, mes, columna, valor_txt.
    """
    def es_mes(c) -> bool:
        if not (isinstance(c, str) and c.strip()):
            return False
        try:
            return subperiodo(c)[0] == "M"
        except ValueError:
            return False

    ancho = max(len(f) for f in filas)
    por_columna = [sum(es_mes(f[c]) for f in filas if c < len(f)) for c in range(ancho)]
    col_mes = max(range(ancho), key=lambda c: por_columna[c])
    if por_columna[col_mes] < 2:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra la columna de meses (serie mensual)")
    anios_por_col = {c: sum(_anio_de(f[c]) is not None and isinstance(f[c], float) for f in filas) for c in range(col_mes)}
    col_anio = max(anios_por_col, key=anios_por_col.get) if anios_por_col else None
    if col_anio is None or anios_por_col[col_anio] < 1:
        raise ValueError(f"Hoja {nombre!r}: no se encuentra la columna de años a la izquierda de los meses")
    primera = col_mes + 1
    candidato, territorio, anio, out = None, None, None, []
    for fila in filas:
        textos = [str(c).strip() for c in fila if isinstance(c, str) and c.strip()]
        if textos and _es_pie(textos[0]):
            break
        valores = fila[primera:]
        if all(_en_blanco(v) for v in valores):
            if len(textos) == 1 and not es_mes(fila[col_mes]):
                if territorio is None:
                    candidato = textos[0]
                else:  # nuevo bloque de territorio tras los datos
                    candidato, territorio, anio = textos[0], None, None
            continue
        if territorio is None:
            if candidato is None:
                raise ValueError(f"Hoja {nombre!r}: datos sin nombre de territorio encima")
            territorio = candidato
        celda_anio = fila[col_anio]
        if es_mes(fila[col_mes]):
            if isinstance(celda_anio, float):
                anio = _anio_de(celda_anio)
            if anio is None:
                raise ValueError(f"Hoja {nombre!r}: mes sin año en {fila[col_mes]!r}")
            mes = subperiodo(fila[col_mes])[1]
            out += [{"hoja": nombre, "territorio_txt": territorio, "anio": anio, "mes": mes, "columna": i,
                     "valor_txt": "" if _en_blanco(v) else _texto_valor(v)} for i, v in enumerate(valores)]
        elif not isinstance(celda_anio, float):
            raise ValueError(f"Hoja {nombre!r}: fila con datos que no es mensual ni anual: {fila[:primera + 2]}")
    if not out:
        raise ValueError(f"Hoja {nombre!r}: no hay filas mensuales (serie mensual)")
    return out


def leer_serie_vertical(path: Path) -> pd.DataFrame:
    """Lee un boletín MIVAU de una hoja con periodos en filas y columnas sin rótulo (09010600, 09011600).

    Formato largo: hoja, territorio_txt, anio, mes, columna, valor_txt (solo filas mensuales; ver
    `_parsear_serie_vertical`). Todas las hojas deben tener la estructura.
    """
    wb = xlrd.open_workbook(str(path))
    filas = []
    for hoja in wb.sheets():
        matriz = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
        filas += _parsear_serie_vertical(hoja.name.strip(), matriz)
    return pd.DataFrame(filas, columns=["hoja", "territorio_txt", "anio", "mes", "columna", "valor_txt"])
