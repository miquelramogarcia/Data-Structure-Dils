"""PROTOTIPOS: construye `Data Dils_v2.xlsx` con las hojas "(prototipo)" de cada prototipos/<tema>/hoja_libro.py.

Uso: python -m prototipos.libro

`python -m etl.ejecutar_todo` NO añade estas hojas: el libro de producción no cambia. Cada tema aporta
`hoja_libro.hojas() -> list[tuple[str, pd.DataFrame]]`.
"""
import importlib
from pathlib import Path

import pandas as pd

from etl.construir_libro import construir_libro

RAIZ = Path(__file__).resolve().parent.parent


def hojas_prototipo(directorio: Path | None = None) -> list[tuple[str, pd.DataFrame]]:
    """Hojas de todos los temas con `hoja_libro.py` (orden alfabético del tema)."""
    directorio = Path(directorio) if directorio else Path(__file__).resolve().parent
    hojas: list[tuple[str, pd.DataFrame]] = []
    for modulo in sorted(directorio.glob("*/hoja_libro.py")):
        hojas += importlib.import_module(f"prototipos.{modulo.parent.name}.hoja_libro").hojas()
    return hojas


def main() -> None:
    construir_libro(RAIZ / "Data Dils.xlsx", RAIZ / "Data Dils_v2.xlsx", hojas_extra=hojas_prototipo())


if __name__ == "__main__":
    main()
