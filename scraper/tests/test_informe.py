"""Estado de cada fuente: una prueba por regla de la tabla.

La distinción que estos tests protegen, y que es la razón de que haya cuatro
estados y no dos:

  INCOMPLETA  es un problema NUESTRO — la fuente publica actividades que no
              logramos leer.
  SIN_EVENTOS es el resultado CORRECTO — la fuente anda y hoy no tiene nada
              gratuito (el Teatro Colón vende entradas).

Confundirlas manda a perder tiempo arreglando lo que funciona, o a ignorar lo
que se rompió.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.informe import (  # noqa: E402
    ERROR,
    INCOMPLETA,
    OK,
    SIN_EVENTOS,
    InformeFuente,
)


def _informe(**kwargs) -> InformeFuente:
    base = dict(id="sala", nombre="Sala X")
    return InformeFuente(**{**base, **kwargs})


# --- las cuatro reglas -----------------------------------------------------

def test_trae_eventos_y_descarta_poco_esta_ok():
    informe = _informe(eventos=20, fichas=27,
                       motivos={"ok": 20, "precio": 6, "fecha": 1})
    assert informe.estado == OK


def test_perder_muchas_fichas_por_algo_corregible_es_incompleta():
    """Caso real: fichas sin título legible porque no tienen h1."""
    informe = _informe(eventos=3, fichas=30, motivos={"ok": 3, "titulo": 20, "fecha": 7})
    assert informe.estado == INCOMPLETA


def test_descartar_mucho_por_precio_no_es_incompleta():
    """Descartar lo pago es el filtro haciendo su trabajo, no una falla."""
    informe = _informe(eventos=5, fichas=30, motivos={"ok": 5, "precio": 25})
    assert informe.estado == OK


def test_responde_pero_no_hay_nada_gratis_es_sin_eventos():
    """Teatro Colón: 38 fichas, 28 dicen «Comprar entradas»."""
    informe = _informe(eventos=0, fichas=38, motivos={"precio": 28, "fecha": 10})
    assert informe.estado == SIN_EVENTOS
    assert "ninguna es gratuita" in informe.detalle


def test_una_excepcion_es_error():
    informe = _informe(error="ConnectTimeout: no responde")
    assert informe.estado == ERROR
    assert informe.detalle == "ConnectTimeout: no responde"


def test_no_leer_ni_una_ficha_es_error_aunque_no_haya_excepcion():
    """El sitio responde 200 pero cambió tanto que no encontramos por dónde
    entrar. Sin esto quedaría como SIN_EVENTOS y pasaría por normal."""
    informe = _informe(eventos=0, fichas=0)
    assert informe.estado == ERROR
    assert "No se pudo leer" in informe.detalle


# --- el detalle es lo que lee una persona ----------------------------------

def test_el_detalle_dice_los_numeros_y_el_porque():
    informe = _informe(eventos=20, fichas=27, motivos={"ok": 20, "precio": 6, "fecha": 1})
    detalle = informe.detalle
    assert "20 eventos de 27 actividades" in detalle
    assert "6 no dicen ser gratuitas" in detalle
    assert "1 sin fecha legible" in detalle


def test_una_fuente_sin_descartes_no_arrastra_parentesis_vacio():
    assert _informe(eventos=5, fichas=5, motivos={"ok": 5}).detalle.endswith(
        "5 eventos de 5 actividades leídas.")


# --- lo que se serializa ---------------------------------------------------

def test_el_dict_no_publica_el_contador_de_exitos():
    """`ok` cuenta las fichas que salieron bien; en «descartadas» sería
    confuso, así que no viaja."""
    publicado = _informe(eventos=2, fichas=3, motivos={"ok": 2, "precio": 1}).to_dict()
    assert publicado["discarded"] == {"precio": 1}
    assert publicado["status"] == OK
    assert publicado["events"] == 2 and publicado["items_read"] == 3
