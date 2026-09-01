"""El experimento del navegador: sólo la parte que se puede probar sin red.

Existe porque el experimento falló dos veces seguidas por errores míos antes
de llegar a responder la pregunta que tenía que responder. Lo que se puede
fijar con un test, se fija.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experimento_navegador import OBJETIVO, url_pedida  # noqa: E402


def test_sin_argumento_usa_el_objetivo():
    assert url_pedida([]) == OBJETIVO


def test_un_argumento_vacio_no_cuenta_como_url():
    """Disparado por push no existe `inputs.url`: el paso pasa "".

    Eso hizo fallar la corrida con 'Cannot navigate to invalid URL'.
    """
    assert url_pedida([""]) == OBJETIVO
    assert url_pedida(["   "]) == OBJETIVO


def test_una_url_de_verdad_gana():
    assert url_pedida(["https://sala.ar/agenda"]) == "https://sala.ar/agenda"
    assert url_pedida(["", "https://sala.ar/x"]) == "https://sala.ar/x"
