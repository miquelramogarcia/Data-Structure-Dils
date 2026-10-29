"""Hoja `Mapeo (prototipo)` del libro: el contenido de mapeo.csv."""
import pandas as pd

from prototipos.linaje.generar import generar_mapeo


def hojas() -> list[tuple[str, pd.DataFrame]]:
    return [("Mapeo (prototipo)", generar_mapeo())]
