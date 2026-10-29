from datetime import date

from etl.lib.periodos import (mes_desde_texto, periodo_anual, periodo_mensual,
                              periodo_trimestral)


def test_periodo_mensual():
    assert periodo_mensual(2026, 6) == {"periodo": "2026M06", "frecuencia": "M", "anio": 2026,
        "trimestre": None, "mes": 6, "fecha": date(2026, 6, 1)}


def test_periodo_trimestral():
    p = periodo_trimestral(2025, 3)
    assert (p["periodo"], p["fecha"], p["mes"]) == ("2025T3", date(2025, 7, 1), None)


def test_periodo_anual():
    assert periodo_anual(2024)["fecha"] == date(2024, 1, 1) and periodo_anual(2024)["periodo"] == "2024"


def test_mes_desde_texto():
    assert [mes_desde_texto(t) for t in ["Ene.", "Sept.", "DICIEMBRE"]] == [1, 9, 12]
