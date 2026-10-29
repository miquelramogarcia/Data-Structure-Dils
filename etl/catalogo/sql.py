"""Generador de CREATE TABLE a partir del catálogo (tablas.csv y campos.csv)."""
from datetime import date
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent
SALIDA = DIR.parent.parent / "sql" / "create_tables.sql"
SALIDA_CARGA = DIR.parent.parent / "sql" / "load_data.sql"
# Los CSV de etl/salida/ terminan siempre en LF (escribir_csv fuerza lineterminator y .gitattributes fija eol=lf).
FIN_LINEA_CSV = "\n"


def cargar_catalogo() -> tuple[pd.DataFrame, pd.DataFrame]:
    tablas = pd.read_csv(DIR / "tablas.csv", dtype=str, keep_default_na=False)
    campos = pd.read_csv(DIR / "campos.csv", dtype=str, keep_default_na=False)
    return tablas, campos


def _lit(txt: str) -> str:
    return str(txt).replace("'", "''")


def create_table_sql(esquema: str, tabla: str, campos: pd.DataFrame, estadistica: str = "") -> str:
    if "tabla" in campos.columns and (campos["tabla"] == tabla).any():
        campos = campos[campos["tabla"] == tabla]
    lineas = []
    for _, c in campos.iterrows():
        nulo = "NOT NULL" if str(c["nulo"]).strip().upper() == "NO" else "NULL"
        generado = str(c.get("generado", "")).strip()
        tipo = f"{c['tipo_mysql']} GENERATED ALWAYS AS ({generado}) STORED" if generado else c["tipo_mysql"]
        lineas.append(f"  `{c['campo']}` {tipo} {nulo} COMMENT '{_lit(c['descripcion'])}'")
    pk = [c["campo"] for _, c in campos.iterrows() if str(c["clave"]).strip().upper() == "PRIMARY KEY"]
    if pk:
        lineas.append("  PRIMARY KEY (" + ", ".join(f"`{p}`" for p in pk) + ")")
    for _, c in campos.iterrows():
        if str(c["clave"]).strip().upper() == "INDEX":
            lineas.append(f"  INDEX `idx_{c['campo']}` (`{c['campo']}`)")
    cuerpo = ",\n".join(lineas)
    return (f"CREATE TABLE IF NOT EXISTS `{esquema}`.`{tabla}` (\n{cuerpo}\n"
            f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci COMMENT='{_lit(estadistica)}';")


def _sql_escapes(txt: str) -> str:
    return txt.replace("\r", "\\r").replace("\n", "\\n")


def load_data_sql(esquema: str, tabla: str, campos: pd.DataFrame, ruta_csv: str | None = None) -> str:
    """LOAD DATA LOCAL INFILE de `etl/salida/<tabla>.csv`.

    MySQL rechaza valores explícitos en columnas generadas: se leen en variables `@omitir_<col>` que no se usan.
    El CSV codifica NULL como campo vacío: las columnas que admiten NULL pasan por `NULLIF(@var, '')`.
    """
    if "tabla" in campos.columns and (campos["tabla"] == tabla).any():
        campos = campos[campos["tabla"] == tabla]
    ruta = ruta_csv or f"etl/salida/{tabla}.csv"
    cols, sets = [], []
    for _, c in campos.iterrows():
        campo = c["campo"]
        if str(c.get("generado", "")).strip():
            cols.append(f"@omitir_{campo}")
        elif str(c["nulo"]).strip().upper() == "NO":
            cols.append(f"`{campo}`")
        else:
            cols.append(f"@{campo}")
            sets.append(f"`{campo}` = NULLIF(@{campo}, '')")
    cierre = ";" if not sets else "\nSET " + ",\n    ".join(sets) + ";"
    return (f"LOAD DATA LOCAL INFILE '{_lit(ruta)}' INTO TABLE `{esquema}`.`{tabla}`\n"
            f"CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '\"' ESCAPED BY '' "
            f"LINES TERMINATED BY '{_sql_escapes(FIN_LINEA_CSV)}'\nIGNORE 1 LINES\n(" + ", ".join(cols) + ")" + cierre)


def descripcion_tabla(tablas: pd.DataFrame, esquema: str, tabla: str) -> str:
    """Comentario de una tabla que puede alimentarse de varios datasets.

    Regla: si tablas.csv tiene la columna opcional `descripcion_tabla` y alguna fila de la tabla la rellena,
    gana la primera no vacía. Si no, es la parte común de las `estadistica` de sus datasets: el prefijo de
    palabras que comparten todas, sin separadores finales (con un solo dataset, su estadística entera).
    """
    grupo = tablas[(tablas["esquema"] == esquema) & (tablas["tabla"] == tabla)]
    if "descripcion_tabla" in grupo.columns:
        escritas = [d for d in grupo["descripcion_tabla"] if str(d).strip()]
        if escritas:
            return str(escritas[0]).strip()
    textos = [str(e).split() for e in grupo["estadistica"]]
    comun = []
    for palabras in zip(*textos):
        if len({w.rstrip(",;") for w in palabras}) != 1:  # "libre," y "libre" cuentan como la misma palabra
            break
        comun.append(palabras[0])
    return " ".join(comun).rstrip(" ,:;-") or (str(grupo["estadistica"].iloc[0]) if len(grupo) else "")


def escribir_sql(salida: Path = SALIDA) -> None:
    tablas, campos = cargar_catalogo()
    con_nombre = tablas[(tablas["esquema"] != "") & (tablas["tabla"] != "")]
    partes = [f"-- Generado por etl/catalogo/sql.py el {date.today().isoformat()}. No editar a mano.\n"]
    for esq in sorted(con_nombre["esquema"].unique()):
        partes.append(f"CREATE SCHEMA IF NOT EXISTS `{esq}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;")
    # una sola sentencia por (esquema, tabla), aunque varios datasets compartan tabla
    for _, t in con_nombre.drop_duplicates(["esquema", "tabla"]).iterrows():
        cs = campos[campos["tabla"] == t["tabla"]]
        if cs.empty:
            partes.append(f"-- {t['esquema']}.{t['tabla']}: pendiente de diseño")
        else:
            partes.append(create_table_sql(t["esquema"], t["tabla"], cs,
                                           descripcion_tabla(tablas, t["esquema"], t["tabla"])))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n\n".join(partes) + "\n", encoding="utf-8")


def escribir_carga(salida: Path = SALIDA_CARGA) -> None:
    """sql/load_data.sql: un LOAD DATA por tabla con datos (estado con_datos), tras create_tables.sql."""
    tablas, campos = cargar_catalogo()
    con_datos = tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]
    partes = [f"-- Generado por etl/catalogo/sql.py el {date.today().isoformat()}. No editar a mano.\n"
              "-- Ejecutar DESPUÉS de create_tables.sql, desde la raíz del proyecto y con local_infile activo\n"
              "-- (servidor: SET GLOBAL local_infile = 1; cliente: mysql --local-infile=1).\n"
              "-- anio, trimestre y mes son columnas generadas: se leen en @omitir_* y MySQL las calcula desde fecha."]
    for _, t in con_datos.drop_duplicates(["esquema", "tabla"]).iterrows():
        partes.append(load_data_sql(t["esquema"], t["tabla"], campos[campos["tabla"] == t["tabla"]]))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n\n".join(partes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    escribir_sql()
    escribir_carga()
