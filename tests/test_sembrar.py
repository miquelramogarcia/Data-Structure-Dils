import pytest

from etl.catalogo import sembrar


def test_sembrar_se_niega_a_sobrescribir_el_catalogo_existente(monkeypatch, tmp_path):
    (tmp_path / "tablas.csv").write_text("x", encoding="utf-8")
    (tmp_path / "campos.csv").write_text("y", encoding="utf-8")
    monkeypatch.setattr(sembrar, "DIR", tmp_path)

    def _no_leer(*a, **k):
        raise AssertionError("no debe leer el Excel")
    monkeypatch.setattr(sembrar, "leer_hoja_usuario", _no_leer)
    with pytest.raises(SystemExit) as e:
        sembrar.sembrar(tmp_path / "x.xlsx")
    assert "--forzar" in str(e.value) and "tablas.csv" in str(e.value)
    assert (tmp_path / "tablas.csv").read_text(encoding="utf-8") == "x"


def test_sembrar_con_forzar_continua(monkeypatch, tmp_path):
    (tmp_path / "tablas.csv").write_text("x", encoding="utf-8")
    monkeypatch.setattr(sembrar, "DIR", tmp_path)

    class _Continua(Exception):
        pass

    def _leer(*a, **k):
        raise _Continua
    monkeypatch.setattr(sembrar, "leer_hoja_usuario", _leer)
    with pytest.raises(_Continua):
        sembrar.sembrar(tmp_path / "x.xlsx", forzar=True)
