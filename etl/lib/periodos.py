"""Construcción de periodos (mensual, trimestral, anual) y lectura de meses en texto."""
import unicodedata
from datetime import date

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def periodo_mensual(anio: int, mes: int) -> dict:
    return {"periodo": f"{anio}M{mes:02d}", "frecuencia": "M", "anio": anio,
            "trimestre": None, "mes": mes, "fecha": date(anio, mes, 1)}


def periodo_trimestral(anio: int, trimestre: int) -> dict:
    return {"periodo": f"{anio}T{trimestre}", "frecuencia": "T", "anio": anio,
            "trimestre": trimestre, "mes": None, "fecha": date(anio, 3 * (trimestre - 1) + 1, 1)}


def periodo_anual(anio: int) -> dict:
    return {"periodo": f"{anio}", "frecuencia": "A", "anio": anio,
            "trimestre": None, "mes": None, "fecha": date(anio, 1, 1)}


def mes_desde_texto(txt: str) -> int:
    """Devuelve el número de mes (1-12) a partir de 'Ene.', 'enero', 'ENE', 'Sept.'..."""
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    t = t.strip().rstrip(".").strip()
    if len(t) >= 3 and t[:3] in _MESES:
        return _MESES.index(t[:3]) + 1
    raise ValueError(f"Mes no reconocido: {txt!r}")
