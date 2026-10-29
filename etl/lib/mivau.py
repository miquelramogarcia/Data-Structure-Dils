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
    ruta.write_bytes(r.content)
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


def subperiodo(txt: str) -> tuple[str, int]:
    """('M', mes) o ('T', trimestre) a partir de 'Ene.', '1T', '3º T', 'Trimestre 1', 'I'-'IV'."""
    t = _norm(txt)
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


def _leer_hoja(hoja) -> list[tuple]:
    filas = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
    # Cabeceras: fila del año y, hasta 3 filas debajo, la del subperiodo.
    for r, fila in enumerate(filas[:40]):
        if not any(_anio_de(c) for c in fila):
            continue
        for rs in range(r + 1, min(r + 4, len(filas))):
            if sum(_es_subperiodo(c) for c in filas[rs]) >= 2:
                break
        else:
            continue
        # Año arrastrado hacia la derecha hasta el siguiente año.
        anios, actual = [], None
        for c in fila:
            actual = _anio_de(c) or actual
            anios.append(actual)
        cols = [(c, anios[c], str(filas[rs][c]).strip()) for c in range(len(filas[rs]))
                if anios[c] and _es_subperiodo(filas[rs][c])]
        col_terr = cols[0][0] - 1
        out = []
        for fila_d in filas[rs + 1:]:
            terr = fila_d[col_terr] if col_terr >= 0 else ""
            if not isinstance(terr, str) or not terr.strip():
                continue
            vals = [(a, s, fila_d[c]) for c, a, s in cols
                    if fila_d[c] != "" and (isinstance(fila_d[c], float) or str(fila_d[c]).strip() in _NULOS)]
            if not any(isinstance(v, float) for _, _, v in vals):
                continue  # nota, fuente o fila sin datos
            out += [(terr.strip(), a, s, _texto_valor(v)) for a, s, v in vals]
        return out
    return []


def leer_matriz(path: Path, hojas: list[str] | None = None) -> pd.DataFrame:
    """Lee un boletín MIVAU y devuelve formato largo: hoja, territorio_txt, anio, subperiodo_txt, valor_txt."""
    wb = xlrd.open_workbook(str(path))
    filas = []
    for nombre in wb.sheet_names():
        if hojas is not None and nombre not in hojas:
            continue
        filas += [(nombre,) + f for f in _leer_hoja(wb.sheet_by_name(nombre))]
    return pd.DataFrame(filas, columns=["hoja", "territorio_txt", "anio", "subperiodo_txt", "valor_txt"])
