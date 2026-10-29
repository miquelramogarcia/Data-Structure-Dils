"""Constructor del libro de salida `Data Dils_v2.xlsx` (catálogo + una hoja por tabla con datos).

Siempre se construye un libro nuevo con openpyxl: nunca se carga ni se escribe `Data Dils.xlsx`.
"""
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from etl.catalogo.sql import DIR as DIR_CATALOGO, cargar_catalogo, create_table_sql, descripcion_tabla
from etl.lib.territorios import cargar_maestro, leer_hoja_con_errores

DIR_SALIDA = Path(__file__).parent / "salida"
GLOSARIO = DIR_CATALOGO / "glosario.csv"
# Las hojas de datos del libro son una MUESTRA de cada tabla (petición del usuario, 2026-10-29): la tabla completa
# es el CSV de etl/salida/, que es lo que se importa a MySQL. Regla de la muestra en `muestra_libro`.
FILAS_MUESTRA_LIBRO = 1000
# Orden de niveles territoriales para la muestra (de mayor a menor); un nivel desconocido va al final.
ORDEN_NIVELES = ["Nacional", "CCAA", "Provincia", "Municipio", "Distrito", "Seccion"]
MAX_HOJA = 31
ANCHO_MAX = 60
ANCHO_CREATE = 100
ALTO_FILA = 15
ERRORES_EXCEL = {"#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}
# Tablas cuyo CSV no se versiona (> 50 MB): si falta (clon recién hecho), su hoja lleva una nota con el comando
# que lo genera en lugar de hacer fallar el libro. Cualquier otro CSV ausente sigue siendo un error.
CSV_NO_VERSIONADOS = {"mivau_serpavi_alquiler": "python -m etl.ejecutar_todo MIVAU-SERPAVI"}
NOTA_KPIS = "Columna vaciada: contenía #VALUE! (fórmulas rotas por vínculo externo perdido)"

FUENTE = Font(name="Arial", size=10)
FUENTE_CAB = Font(name="Arial", size=10, bold=True)
FUENTE_ENLACE = Font(name="Arial", size=10, color="0563C1", underline="single")
RELLENO_CAB = PatternFill("solid", start_color="D9D9D9", end_color="D9D9D9")
FORMATO_FECHA = "yyyy-mm-dd"
TIPOS_NUMERICOS = ("INT", "SMALLINT", "TINYINT", "MEDIUMINT", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE")


def nombre_hoja(tabla: str, usados: set[str]) -> str:
    """Recorta a 31 caracteres y desempata con ~2, ~3… (Excel no distingue mayúsculas)."""
    ocupados = {u.lower() for u in usados}
    cand = tabla[:MAX_HOJA]
    n = 1
    while cand.lower() in ocupados:
        n += 1
        suf = f"~{n}"
        cand = tabla[:MAX_HOJA - len(suf)] + suf
    return cand


def _py(v):
    """Valor de pandas/numpy a valor Python escribible (NaN/NaT a None)."""
    if v is None:
        return None
    if not isinstance(v, (str, date)) and pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if hasattr(v, "item"):
        return v.item()
    return v


def _tipar(df: pd.DataFrame, campos: pd.DataFrame) -> tuple[pd.DataFrame, set[str]]:
    """Convierte las columnas leídas como texto según tipo_mysql. Devuelve (df, columnas fecha)."""
    tipos = dict(zip(campos["campo"], campos["tipo_mysql"].str.upper()))
    fechas: set[str] = set()
    df = df.copy()
    for c in df.columns:
        t = tipos.get(c, "")
        if t == "DATE":
            df[c] = pd.to_datetime(df[c], format="%Y-%m-%d").dt.date
            fechas.add(c)
        elif t.startswith(TIPOS_NUMERICOS):
            df[c] = pd.to_numeric(df[c])
    return df, fechas


def _escribir(wb: Workbook, nombre: str, df: pd.DataFrame, *, fechas=(), nota: str | None = None,
              ancho_fijo: dict[str, int] | None = None, ajustar=frozenset(), superior: bool = False):
    """Hoja con estilo común: cabecera en negrita con relleno, cabecera inmovilizada, autofiltro, anchos."""
    ws = wb.create_sheet(nombre)
    fila_cab = 2 if nota else 1
    if nota:
        ws.cell(1, 1, nota).font = FUENTE_CAB
    cols = list(df.columns)
    for j, c in enumerate(cols, 1):
        cel = ws.cell(fila_cab, j, c)
        cel.font, cel.fill = FUENTE_CAB, RELLENO_CAB
        cel.alignment = Alignment(vertical="top" if superior else "center")
    textos = {j for j, c in enumerate(cols, 1) if str(c).startswith("cod_")}
    # Sin ajuste de texto: todas las filas con la misma altura (petición del usuario, 2026-10-29).
    envolver = Alignment(vertical="top", wrap_text=False)
    arriba = Alignment(vertical="top")
    for i, fila in enumerate(df.astype(object).itertuples(index=False, name=None), fila_cab + 1):
        for j, v in enumerate(fila, 1):
            v = _py(v)
            if v is None:
                continue
            cel = ws.cell(i, j, v)
            cel.font = FUENTE
            if j in textos:
                cel.number_format = "@"
            elif cols[j - 1] in fechas:
                cel.number_format = FORMATO_FECHA
            if superior:
                cel.alignment = envolver if cols[j - 1] in ajustar else arriba
    ws.sheet_format.defaultRowHeight = ALTO_FILA
    ws.sheet_format.customHeight = True
    if cols:
        ws.freeze_panes = ws.cell(fila_cab + 1, 1)
        ws.auto_filter.ref = f"A{fila_cab}:{get_column_letter(len(cols))}{fila_cab + len(df)}"
    for j, c in enumerate(cols, 1):
        if ancho_fijo and c in ancho_fijo:
            ancho = ancho_fijo[c]
        elif c in fechas:
            ancho = 12
        else:
            ancho = max([len(str(c)) + 2] + [min(len(str(v)), ANCHO_MAX) + 2 for v in df[c].head(200).dropna()])
        tope = ancho if ancho_fijo and c in ancho_fijo else ANCHO_MAX
        ws.column_dimensions[get_column_letter(j)].width = min(max(ancho, 8), tope)
    return ws


def _hoja_tablas(wb, tablas, campos, hojas, filas) -> None:
    cab = ["Esquema", "Tabla My SQL", "Estadística", "Origen", "Fuente", "Frecuencia", "Formato Origen",
           "Prioridad", "Estado", "Filas", "CREATE TABLE"]
    reg = []
    for _, t in tablas.iterrows():
        sql = ""
        if t["esquema"] and t["tabla"]:
            cs = campos[campos["tabla"] == t["tabla"]]
            if not cs.empty:
                sql = create_table_sql(t["esquema"], t["tabla"], cs, descripcion_tabla(tablas, t["esquema"], t["tabla"]))
        reg.append([t["esquema"] or None, t["tabla"] or None, t["estadistica"], t["origen"], t["fuente"],
                    t["frecuencia"], t["formato_origen"], t["prioridad"], t["estado"],
                    filas.get(t["dataset_id"]), sql or None])
    ws = _escribir(wb, "Tablas", pd.DataFrame(reg, columns=cab), superior=True, ajustar=set(cab),
                   ancho_fijo={"CREATE TABLE": ANCHO_CREATE, "Estadística": 50, "Fuente": 40, "Origen": 30,
                               "Tabla My SQL": 40, "Esquema": 12})
    for i, (_, t) in enumerate(tablas.iterrows(), 2):
        hoja = hojas.get(t["dataset_id"])
        if hoja:
            cel = ws.cell(i, 2)
            cel.hyperlink = Hyperlink(ref=cel.coordinate, location="'" + hoja.replace("'", "''") + "'!A1")
            cel.font = FUENTE_ENLACE


def _hoja_general(wb, origen: Path) -> tuple[int, int]:
    """Copia la hoja General del usuario sin la columna KPIs ni celdas de error.

    Devuelve (errores en KPIs, errores en el resto de columnas); ambos se vacían.
    """
    df = leer_hoja_con_errores(origen, "General")
    err_kpis = 0
    if "KPIs" in df.columns:
        err_kpis = int(df["KPIs"].map(_es_error).sum())
        df["KPIs"] = None
    errores = 0
    for c in df.columns:
        for i, v in df[c].items():
            if _es_error(v):
                df.at[i, c] = None
                errores += 1
    ws = _escribir(wb, "General", df, superior=True, ajustar=set(df.columns))
    if "KPIs" in df.columns:
        ws.cell(1, list(df.columns).index("KPIs") + 1).comment = Comment(NOTA_KPIS, "Claude", width=320, height=60)
    return err_kpis, errores


def _es_error(v) -> bool:
    return isinstance(v, str) and v.strip() in ERRORES_EXCEL


def muestra_libro(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Muestra estable y representativa de una tabla para su hoja del libro (como mucho `n` filas).

    1. Orden: `fecha` descendente (lo más reciente primero), `nivel` según ORDEN_NIVELES, `cod_territorio` e
       `id_registro` (las columnas que falten se omiten; sin ninguna, se respeta el orden del CSV).
    2. Cada nivel presente recibe una cuota de n // nº de niveles filas (sus primeras en ese orden), para que
       aparezcan todos los niveles territoriales aunque el más fino tenga muchas más filas; lo que sobre (niveles
       con menos filas que la cuota) se rellena con las siguientes filas en el mismo orden.
    3. La muestra se presenta en ese mismo orden. No depende del orden de entrada ni de nada aleatorio.
    """
    d = df.reset_index(drop=True)
    aux = pd.DataFrame(index=d.index)
    ascendente = []
    if "fecha" in d.columns:
        aux["fecha"] = d["fecha"].astype(str)
        ascendente.append(False)
    if "nivel" in d.columns:
        aux["nivel"] = d["nivel"].map({v: i for i, v in enumerate(ORDEN_NIVELES)}).fillna(len(ORDEN_NIVELES))
        ascendente.append(True)
    for c in ("cod_territorio", "id_registro"):
        if c in d.columns:
            aux[c] = d[c].astype(str)
            ascendente.append(True)
    orden = list(aux.sort_values(list(aux.columns), ascending=ascendente, kind="stable").index
                 if ascendente else d.index)
    if len(orden) > n:
        if "nivel" in aux.columns:
            niveles = aux.loc[orden, "nivel"]
            elegidas = set(niveles.groupby(niveles, sort=False).head(n // niveles.nunique()).index)
            for i in orden:                      # relleno con las siguientes filas en el mismo orden
                if len(elegidas) >= n:
                    break
                elegidas.add(i)
            orden = [i for i in orden if i in elegidas]
        else:
            orden = orden[:n]
    return d.loc[orden].reset_index(drop=True)


def _hoja_datos(wb, tabla: str, hoja: str, campos: pd.DataFrame, dir_salida: Path) -> int | None:
    """Escribe la hoja de una tabla (completa o muestra) y devuelve el total de filas del CSV (None si es un CSV
    no versionado que aún no se ha generado)."""
    csv = dir_salida / f"{tabla}.csv"
    if not csv.exists():
        if tabla in CSV_NO_VERSIONADOS:
            nota = (f"Falta etl/salida/{tabla}.csv (no se versiona por tamaño): generarlo con "
                    f"{CSV_NO_VERSIONADOS[tabla]} y reconstruir el libro")
            print(f"AVISO: {nota}")
            _escribir(wb, hoja, pd.DataFrame(columns=list(campos["campo"])), nota=nota).sheet_state = "hidden"
            return None
        raise FileNotFoundError(f"Falta el CSV de salida de {tabla}: {csv}")
    df = pd.read_csv(csv, sep=";", dtype=str, encoding="utf-8")
    total = len(df)
    df = muestra_libro(df, FILAS_MUESTRA_LIBRO)
    nota = f"Muestra: {len(df)} de {total} filas. La tabla completa está en etl/salida/{tabla}.csv"
    df, fechas = _tipar(df, campos)
    # Hojas de import ocultas (petición del usuario, 2026-10-29); se muestran con clic derecho > Mostrar.
    _escribir(wb, hoja, df, fechas=fechas, nota=nota).sheet_state = "hidden"
    return total


def construir_libro(origen: Path = Path("Data Dils.xlsx"), salida: Path = Path("Data Dils_v2.xlsx"), *,
                    dir_salida: Path | None = None,
                    catalogo: tuple[pd.DataFrame, pd.DataFrame] | None = None) -> None:
    dir_salida = dir_salida or DIR_SALIDA
    tablas, campos = catalogo or cargar_catalogo()
    tablas = tablas.sort_values("dataset_id", kind="stable").reset_index(drop=True)

    con_datos = tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]
    usados: set[str] = set()
    hoja_de_tabla: dict[str, str] = {}   # varios datasets pueden volcar a la misma tabla: una sola hoja
    for _, t in con_datos[con_datos["hoja"] != ""].iterrows():       # los nombres ya fijados, primero
        if hoja_de_tabla.setdefault(t["tabla"], t["hoja"]) == t["hoja"]:
            usados.add(t["hoja"])
    for _, t in con_datos[con_datos["hoja"] == ""].iterrows():
        if t["tabla"] not in hoja_de_tabla:
            hoja_de_tabla[t["tabla"]] = nombre_hoja(t["tabla"], usados)
            usados.add(hoja_de_tabla[t["tabla"]])
    hojas = {t["dataset_id"]: hoja_de_tabla[t["tabla"]] for _, t in con_datos.iterrows()}

    wb = Workbook()
    wb.remove(wb.active)
    filas: dict[str, int] = {}
    total_de_tabla: dict[str, int] = {}
    # Tablas necesita el nº de filas: se escriben antes las hojas de datos y se reordenan al final.
    for tabla, hoja in hoja_de_tabla.items():
        total_de_tabla[tabla] = _hoja_datos(wb, tabla, hoja, campos[campos["tabla"] == tabla], dir_salida)
    for _, t in con_datos.iterrows():
        filas[t["dataset_id"]] = total_de_tabla[t["tabla"]]
    _hoja_tablas(wb, tablas, campos, hojas, filas)
    _escribir(wb, "Campos", campos.rename(columns={
        "tabla": "TABLA", "campo": "Campo", "tipo_mysql": "Tipo MySQL", "nulo": "Nulo", "clave": "Clave",
        "descripcion": "Descripción", "ejemplo": "Ejemplo", "generado": "Generada como"}), superior=True, ajustar={"Descripción"})
    _escribir(wb, "Maestro Territorios", cargar_maestro(origen))
    if GLOSARIO.exists():
        glo = pd.read_csv(GLOSARIO, dtype=str, keep_default_na=False)
    else:
        glo = pd.DataFrame(columns=["termino", "definicion", "fuente"])
    _escribir(wb, "Glosario", glo.rename(columns={"termino": "Término", "definicion": "Definición",
                                                  "fuente": "Fuente"}), superior=True, ajustar={"Definición"})
    err_kpis, errores = _hoja_general(wb, origen)

    orden = ["Tablas", "Campos", "Maestro Territorios", "Glosario", "General"] + list(hoja_de_tabla.values())
    wb._sheets = [wb[n] for n in orden]
    wb.active = 0
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = ws.title == "Tablas"
    wb.save(salida)
    print(f"Libro escrito en {salida}: {len(orden)} hojas; "
          f"General: {err_kpis} celdas con error en la columna KPIs (vaciada) y "
          f"{errores} celdas con error de Excel vaciadas en el resto de columnas")
