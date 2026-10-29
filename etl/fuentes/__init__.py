"""Registro de fuentes: DATASET_ID -> módulo con DATASET_ID, TABLA, DIMENSIONES, MEDIDAS y ejecutar()."""
from etl.fuentes import mivau_31205000

REGISTRO = {m.DATASET_ID: m for m in (mivau_31205000,)}
