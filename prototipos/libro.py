"""PROTOTIPOS: construye `Data Dils_v2.xlsx` con los prototipos incluidos.

Uso: python -m prototipos.libro

`python -m etl.ejecutar_todo` NO añade nada de esto: el libro de producción no cambia. Dos mecanismos:
- Hojas sueltas "(prototipo)": cada prototipos/<tema>/hoja_libro.py aporta `hojas() -> list[tuple[str, DataFrame]]`.
- Tablas de prototipo en el catálogo: cada prototipos/<tema>/catalogo.py aporta
  `catalogo() -> (tablas_df, campos_df, {tabla: ruta_csv})`. Esas filas se añaden SOLO EN MEMORIA al catálogo de
  producción, así salen en las hojas Tablas y Campos y tienen su hoja de datos como cualquier tabla; los CSV de
  etl/catalogo/ no se tocan.
"""
import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.construir_libro import DIR_SALIDA, construir_libro

RAIZ = Path(__file__).resolve().parent.parent


def hojas_prototipo(directorio: Path | None = None) -> list[tuple[str, pd.DataFrame]]:
    """Hojas de todos los temas con `hoja_libro.py` (orden alfabético del tema)."""
    directorio = Path(directorio) if directorio else Path(__file__).resolve().parent
    hojas: list[tuple[str, pd.DataFrame]] = []
    for modulo in sorted(directorio.glob("*/hoja_libro.py")):
        hojas += importlib.import_module(f"prototipos.{modulo.parent.name}.hoja_libro").hojas()
    return hojas


def catalogo_con_prototipos(directorio: Path | None = None):
    """Catálogo de producción + las tablas de los temas con `catalogo.py` (en memoria) y sus CSV."""
    directorio = Path(directorio) if directorio else Path(__file__).resolve().parent
    tablas, campos = cargar_catalogo()
    csvs: dict[str, Path] = {}
    for modulo in sorted(directorio.glob("*/catalogo.py")):
        t, c, rutas = importlib.import_module(f"prototipos.{modulo.parent.name}.catalogo").catalogo()
        ids = set(t["dataset_id"])
        tablas = pd.concat([tablas[~tablas["dataset_id"].isin(ids)], t], ignore_index=True)
        campos = pd.concat([campos[~campos["tabla"].isin(set(c["tabla"]))], c], ignore_index=True)
        csvs.update(rutas)
    return (tablas.fillna(""), campos.fillna("")), csvs


def main() -> None:
    catalogo, csvs = catalogo_con_prototipos()
    # Carpeta temporal con los CSV de producción (enlaces duros: no se copia SERPAVI) + los de los prototipos.
    with tempfile.TemporaryDirectory(dir=RAIZ) as tmp:
        tmp = Path(tmp)
        for csv in DIR_SALIDA.glob("*.csv"):
            try:
                os.link(csv, tmp / csv.name)
            except OSError:
                shutil.copy2(csv, tmp / csv.name)
        for tabla, ruta in csvs.items():
            shutil.copy2(ruta, tmp / f"{tabla}.csv")
        construir_libro(RAIZ / "Data Dils.xlsx", RAIZ / "Data Dils_v2.xlsx", dir_salida=tmp, catalogo=catalogo,
                        hojas_extra=hojas_prototipo())


if __name__ == "__main__":
    main()
