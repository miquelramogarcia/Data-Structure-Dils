from pathlib import Path

from etl.herramientas.extraer_imagenes_xls import extraer

FIXTURES = Path(__file__).parent / "fixtures"
IMG = Path(__file__).parent.parent / "docs" / "fuentes" / "img"


def test_extrae_cabecera_png_y_gif(tmp_path):
    fin = extraer(FIXTURES / "09011600.xls", tmp_path / "a")
    assert [p.suffix for p in fin] == [".jpg", ".png"]
    assert fin[1].read_bytes() == (IMG / "MIVAU-BOL09-FINOBRA_cabecera.png").read_bytes()
    assert fin[1].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    vis = extraer(FIXTURES / "09010600.xls", tmp_path / "b")
    assert [p.suffix for p in vis] == [".jpg", ".gif"]
    assert vis[1].read_bytes() == (IMG / "MIVAU-BOL09-VISADOS_cabecera.gif").read_bytes()
    assert vis[1].read_bytes()[:6] == b"GIF89a"
