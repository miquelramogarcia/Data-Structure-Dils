import pandas as pd
import pytest

from etl import ejecutar_todo


class _Rota:
    DATASET_ID, TABLA, DIMENSIONES, MEDIDAS = "FAKE-ROTA", "t_rota", [], ["v"]

    @staticmethod
    def ejecutar(fecha):
        raise RuntimeError("fuente caída")


class _Buena:
    DATASET_ID, TABLA, DIMENSIONES, MEDIDAS = "FAKE-OK", "t_ok", [], ["v"]
    llamadas = 0

    @classmethod
    def ejecutar(cls, fecha):
        cls.llamadas += 1
        return pd.DataFrame({"nivel": ["Nacional"], "cod_territorio": ["ES"], "periodo": ["2026M01"], "v": [1]})


def test_continua_tras_fallo_construye_libro_y_sale_con_1(monkeypatch, capsys):
    construido = []
    monkeypatch.setattr(ejecutar_todo, "REGISTRO", {"FAKE-ROTA": _Rota, "FAKE-OK": _Buena})
    monkeypatch.setattr(ejecutar_todo, "construir_libro", lambda *a: construido.append(a))
    with pytest.raises(SystemExit) as e:
        ejecutar_todo.main(["FAKE-ROTA", "FAKE-OK"])
    assert e.value.code == 1
    assert _Buena.llamadas == 1 and len(construido) == 1
    out = capsys.readouterr()
    assert "ERROR FAKE-ROTA: fuente caída" in out.err
    assert "OK FAKE-OK: t_ok (1 filas)" in out.out and "FALLO FAKE-ROTA" in out.out


def test_sin_fallos_no_sale_con_error(monkeypatch):
    monkeypatch.setattr(ejecutar_todo, "REGISTRO", {"FAKE-OK": _Buena})
    monkeypatch.setattr(ejecutar_todo, "construir_libro", lambda *a: None)
    ejecutar_todo.main(["FAKE-OK"])


def test_fuente_sin_cuadre_no_lo_ejecuta(monkeypatch, capsys):
    class _Media(_Buena):
        CUADRE = False

    def _no(*a, **k):
        raise AssertionError("cuadre_jerarquico no debe ejecutarse")
    monkeypatch.setattr(ejecutar_todo, "REGISTRO", {"FAKE-MEDIA": _Media})
    monkeypatch.setattr(ejecutar_todo, "construir_libro", lambda *a: None)
    monkeypatch.setattr(ejecutar_todo, "cuadre_jerarquico", _no)
    ejecutar_todo.main(["FAKE-MEDIA"])
    assert "cuadre no aplica" in capsys.readouterr().out


def test_fallo_del_libro_no_oculta_el_resumen(monkeypatch, capsys):
    def _rompe(*a):
        raise RuntimeError("libro bloqueado")
    monkeypatch.setattr(ejecutar_todo, "REGISTRO", {"FAKE-OK": _Buena})
    monkeypatch.setattr(ejecutar_todo, "construir_libro", _rompe)
    with pytest.raises(SystemExit) as e:
        ejecutar_todo.main(["FAKE-OK"])
    assert e.value.code == 1
    out = capsys.readouterr()
    assert "ERROR libro: libro bloqueado" in out.err
    assert "Resumen: 1 correctas, 0 fallidas" in out.out and "OK FAKE-OK" in out.out
