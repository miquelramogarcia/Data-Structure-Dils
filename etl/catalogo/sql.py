"""Generador de CREATE TABLE a partir del catálogo (tablas.csv y campos.csv)."""
from datetime import date
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent
SALIDA = DIR.parent.parent / "sql" / "create_tables.sql"


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
        lineas.append(f"  `{c['campo']}` {c['tipo_mysql']} {nulo} COMMENT '{_lit(c['descripcion'])}'")
    pk = [c["campo"] for _, c in campos.iterrows() if str(c["clave"]).strip().upper() == "PRIMARY KEY"]
    if pk:
        lineas.append("  PRIMARY KEY (" + ", ".join(f"`{p}`" for p in pk) + ")")
    for _, c in campos.iterrows():
        if str(c["clave"]).strip().upper() == "INDEX":
            lineas.append(f"  INDEX `idx_{c['campo']}` (`{c['campo']}`)")
    cuerpo = ",\n".join(lineas)
    return (f"CREATE TABLE IF NOT EXISTS `{esquema}`.`{tabla}` (\n{cuerpo}\n"
            f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci COMMENT='{_lit(estadistica)}';")


def escribir_sql(salida: Path = SALIDA) -> None:
    tablas, campos = cargar_catalogo()
    con_nombre = tablas[(tablas["esquema"] != "") & (tablas["tabla"] != "")]
    partes = [f"-- Generado por etl/catalogo/sql.py el {date.today().isoformat()}. No editar a mano.\n"]
    for esq in sorted(con_nombre["esquema"].unique()):
        partes.append(f"CREATE SCHEMA IF NOT EXISTS `{esq}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;")
    for _, t in con_nombre.iterrows():
        cs = campos[campos["tabla"] == t["tabla"]]
        if cs.empty:
            partes.append(f"-- {t['esquema']}.{t['tabla']}: pendiente de diseño")
        else:
            partes.append(create_table_sql(t["esquema"], t["tabla"], cs, t["estadistica"]))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n\n".join(partes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    escribir_sql()
