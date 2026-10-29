"""Maestro de territorios: carga, resolución de nombres y expansión de uniprovinciales."""
import re
import shutil
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

COLUMNAS_MAESTRO = ["alias", "nivel", "cod_territorio", "cod_ccaa", "nombre_ccaa", "cod_provincia",
                    "nombre_provincia", "cod_municipio", "nombre_municipio", "nombre_territorio",
                    "fuente_alias", "cod_fuente_alias"]
COLUMNAS_TERRITORIO = ["nivel", "cod_territorio", "cod_ccaa", "nombre_ccaa", "cod_provincia",
                       "nombre_provincia", "cod_municipio", "nombre_municipio"]
CCAA_UNIPROVINCIALES = {"03", "04", "06", "13", "14", "15", "17", "18", "19"}
EXTRA_CSV = Path(__file__).with_name("territorios_extra.csv")
# Municipios del INE (relación oficial a 1-1-2026), generado por etl/lib/municipios_ine_generar.py
MUNICIPIOS_CSV = Path(__file__).with_name("municipios_ine.csv")


class TerritorioDesconocido(ValueError):
    """El texto no corresponde a ningún territorio del maestro."""


class TerritorioAmbiguo(ValueError):
    """El texto corresponde a varios territorios distintos y nada permite elegir uno."""


def normalizar(txt: str) -> str:
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


@contextmanager
def copia_temporal(xlsx: Path):
    """Entrega la ruta de una copia temporal del libro (el original no se toca ni se bloquea)."""
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "copia.xlsx"
        shutil.copy(xlsx, copia)
        yield copia


def leer_hoja_usuario(xlsx: Path, hoja: str, **kw) -> pd.DataFrame:
    """Lee una hoja del libro del usuario desde una copia temporal (el original no se toca)."""
    with copia_temporal(xlsx) as copia:
        return pd.read_excel(copia, sheet_name=hoja, **kw)


def leer_hoja_con_errores(xlsx: Path, hoja: str) -> pd.DataFrame:
    """Como leer_hoja_usuario, pero las celdas de error llegan como texto ('#VALUE!', '#REF!'…).

    pandas convierte esas celdas en NaN y no se pueden contar; openpyxl las entrega tal cual.
    Primera fila = cabecera; se descartan columnas sin cabecera y filas totalmente vacías.
    """
    from openpyxl import load_workbook
    with copia_temporal(xlsx) as copia:
        wb = load_workbook(copia, read_only=True, data_only=True)
        try:
            filas = [list(f) for f in wb[hoja].iter_rows(values_only=True)]
        finally:
            wb.close()
    cab = filas[0] if filas else []
    validas = [j for j, c in enumerate(cab) if c is not None]
    datos = [[f[j] if j < len(f) else None for j in validas] for f in filas[1:]]
    datos = [f for f in datos if any(v is not None for v in f)]
    return pd.DataFrame(datos, columns=[cab[j] for j in validas], dtype=object)


def cargar_maestro(xlsx: Path) -> pd.DataFrame:
    """Lee la hoja 'Maestro Territorios' desde una copia temporal y añade territorios_extra.csv y los municipios del INE."""
    df = leer_hoja_usuario(xlsx, "Maestro Territorios", header=None, dtype=str)
    if len(df) and str(df.iloc[0, 0]).strip().lower() == "alias":
        df = df.iloc[1:]
    df = df.iloc[:, :len(COLUMNAS_MAESTRO)].copy()
    df.columns = COLUMNAS_MAESTRO
    extra = pd.read_csv(EXTRA_CSV, dtype=str)
    if len(extra):
        df = pd.concat([df, extra[COLUMNAS_MAESTRO]], ignore_index=True)
    municipios = pd.read_csv(MUNICIPIOS_CSV, dtype=str)
    df = pd.concat([df, municipios[COLUMNAS_MAESTRO]], ignore_index=True)
    return df.reset_index(drop=True)


_ARTICULOS = r"(?:el|la|los|las|lo|l'|els|les|a|o|as|os)"
_RE_ART_PARENTESIS = re.compile(rf"^(?P<resto>.+?)\s*\(\s*(?P<art>{_ARTICULOS})\s*\)$")
_RE_ART_COMA = re.compile(rf"^(?P<resto>.+?)\s*,\s*(?P<art>{_ARTICULOS})$")
_RANGO_NIVEL = {"CCAA": 0, "Provincia": 1}  # preferencia sin nivel: CCAA > Provincia > el resto (Municipio...)
_INDICES: dict[int, tuple] = {}


def clave_municipio(txt: str) -> str:
    """Clave de comparación de un municipio: sin tildes ni mayúsculas y con el artículo al principio.

    "Ejido (El)", "Ejido, El" y "El Ejido" dan "el ejido"; "Palmas de Gran Canaria (Las)" da
    "las palmas de gran canaria". Solo se usa con nivel Municipio (provincias y CCAA no cambian).
    """
    t = normalizar(txt)
    m = _RE_ART_PARENTESIS.match(t) or _RE_ART_COMA.match(t)
    if m:
        art = m.group("art")
        t = art + m.group("resto") if art.endswith("'") else f"{art} {m.group('resto')}"
    return t


def _indice(maestro: pd.DataFrame) -> dict:
    """Columnas normalizadas del maestro, calculadas una vez por DataFrame (resolver se llama muchas veces)."""
    en_cache = _INDICES.get(id(maestro))
    if en_cache is not None and en_cache[0] is maestro and en_cache[1] == len(maestro):
        return en_cache[2]
    alias = maestro["alias"].map(lambda x: normalizar(x) if pd.notna(x) else "").to_numpy()
    nombre = maestro["nombre_territorio"].map(lambda x: normalizar(x) if pd.notna(x) else "").to_numpy()
    es_mu = (maestro["nivel"] == "Municipio").to_numpy()
    mu_map: dict[str, list[int]] = {}
    for pos in es_mu.nonzero()[0]:
        for col in ("alias", "nombre_territorio"):
            valor = maestro.iloc[pos][col]
            if pd.isna(valor):
                continue
            # nombre completo y cada parte de los nombres bilingües ("Alcoy/Alcoi" -> "alcoy", "alcoi")
            for k in {clave_municipio(valor), *(clave_municipio(p) for p in str(valor).split("/"))}:
                if k and pos not in mu_map.setdefault(k, []):
                    mu_map[k].append(pos)
    idx = {"alias": alias, "nombre": nombre, "mu_map": mu_map, "nivel": maestro["nivel"].to_numpy()}
    _INDICES[id(maestro)] = (maestro, len(maestro), idx)
    return idx


def _fila(maestro: pd.DataFrame, pos: int) -> dict:
    fila = maestro.iloc[pos]
    return {c: (None if pd.isna(fila[c]) else fila[c]) for c in COLUMNAS_TERRITORIO}


def _elegir(maestro: pd.DataFrame, posiciones, texto: str, nivel: str | None, contexto: str = "") -> dict:
    """Una sola fila entre las candidatas: sin nivel prefiere CCAA, luego Provincia; si quedan varios
    territorios distintos (mismo nombre en dos provincias) falla en lugar de elegir uno."""
    pos = list(posiciones)
    if nivel is None and pos:
        rangos = {p: _RANGO_NIVEL.get(maestro.iloc[p]["nivel"], 2) for p in pos}
        mejor = min(rangos.values())
        pos = [p for p in pos if rangos[p] == mejor]
    codigos = sorted({maestro.iloc[p]["cod_territorio"] for p in pos})
    if len(codigos) > 1:
        raise TerritorioAmbiguo(f"Territorio ambiguo en el maestro: {texto!r}{contexto} corresponde a "
                                f"{', '.join(codigos[:6])}; hace falta la provincia o el nivel")
    return _fila(maestro, pos[0])


def _candidatas(maestro: pd.DataFrame, texto: str, nivel: str | None):
    idx = _indice(maestro)
    clave = normalizar(texto)
    coincide = (idx["alias"] == clave) | (idx["nombre"] == clave)
    if nivel is not None:
        coincide &= idx["nivel"] == nivel
    pos = coincide.nonzero()[0]
    if nivel == "Municipio":
        claves = {clave_municipio(texto), *(clave_municipio(p) for p in str(texto).split("/"))}
        pos = sorted({*pos, *(q for k in claves for q in idx["mu_map"].get(k, []))})
    return pos


def resolver(maestro: pd.DataFrame, texto: str, nivel: str | None = None) -> dict:
    """Fila del maestro para `texto` (sin tildes ni mayúsculas); TerritorioDesconocido si no existe.

    Sin `nivel`, si el nombre sirve a varios niveles gana CCAA > Provincia > Municipio. Con nivel
    "Municipio" el artículo puede ir al principio o al final ("Ejido (El)" = "El Ejido") y vale cualquiera de
    las dos partes de un nombre bilingüe ("Alcoy" o "Alcoi" para "Alcoy/Alcoi"). Un nombre de
    municipio repetido en varias provincias da TerritorioAmbiguo; usa `resolver_municipio`.
    """
    pos = _candidatas(maestro, texto, nivel)
    if len(pos) == 0:
        raise TerritorioDesconocido(f"Territorio no encontrado en el maestro: {texto!r}")
    return _elegir(maestro, pos, texto, nivel)


def resolver_municipio(maestro: pd.DataFrame, municipio: str, provincia: str) -> dict:
    """Municipio por nombre dentro de una provincia (resuelve nombres repetidos entre provincias).

    TerritorioDesconocido si la provincia no existe o el municipio no está en ella.
    """
    prov = resolver(maestro, provincia, nivel="Provincia")
    pos = [p for p in _candidatas(maestro, municipio, "Municipio")
           if maestro.iloc[p]["cod_provincia"] == prov["cod_provincia"]]
    if not pos:
        raise TerritorioDesconocido(f"Municipio no encontrado en la provincia: {municipio!r} en {provincia!r}")
    return _elegir(maestro, pos, municipio, "Municipio", f" en {provincia!r}")


def _clave(fila: pd.Series, cols: list[str]) -> tuple:
    return tuple(None if pd.isna(fila[c]) else fila[c] for c in cols)


def expandir_uniprovinciales(df: pd.DataFrame, maestro: pd.DataFrame,
                             claves: list[str] | None = None) -> pd.DataFrame:
    """Añade la fila de provincia (copiando la de la CCAA) en las CCAA uniprovinciales si falta.

    La clave de deduplicación es la CCAA más `claves` (dimensiones + periodo). Si es None, se usan
    todas las columnas no territoriales que no sean numéricas (las medidas nunca entran en la clave).
    """
    if claves is None:
        otras = [c for c in df.columns if c not in COLUMNAS_TERRITORIO
                 and not pd.api.types.is_numeric_dtype(df[c])]
    else:
        otras = list(claves)
    existentes = {(f["cod_ccaa"],) + _clave(f, otras) for _, f in df[df["nivel"] == "Provincia"].iterrows()}
    nuevas = []
    for _, f in df[(df["nivel"] == "CCAA") & df["cod_ccaa"].isin(CCAA_UNIPROVINCIALES)].iterrows():
        k = (f["cod_ccaa"],) + _clave(f, otras)
        if k in existentes:
            continue
        prov = maestro[(maestro["nivel"] == "Provincia") & (maestro["cod_ccaa"] == f["cod_ccaa"])]
        if prov.empty:
            continue
        nueva = f.copy()
        for c in COLUMNAS_TERRITORIO:
            nueva[c] = prov.iloc[0][c]
        nuevas.append(nueva)
        existentes.add(k)
    if not nuevas:
        return df
    return pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
