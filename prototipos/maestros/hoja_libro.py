"""Hoja `Maestros (prototipo)` del libro: el DDL de los maestros, una línea por fila."""
import pandas as pd

from prototipos.maestros.generar import generar_ddl


def hojas() -> list[tuple[str, pd.DataFrame]]:
    lineas = generar_ddl().splitlines()
    return [("Maestros (prototipo)", pd.DataFrame({"linea": range(1, len(lineas) + 1), "DDL": lineas}))]
