"""Registro de fuentes: DATASET_ID -> módulo con DATASET_ID, TABLA, DIMENSIONES, MEDIDAS y ejecutar()."""
from etl.fuentes import (mivau_31205000, mivau_32100500, mivau_32101000, mivau_34010110,
                         mivau_340101g0)

REGISTRO = {m.DATASET_ID: m for m in (mivau_31205000, mivau_32100500, mivau_32101000, mivau_34010110,
                                      mivau_340101g0)}
