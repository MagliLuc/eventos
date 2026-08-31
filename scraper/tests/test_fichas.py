"""Lectura de fichas: el mecanismo que reemplaza a los selectores CSS.

Varias fuentes daban 200 sin marcado porque el listado se arma por
JavaScript, pero la ficha de cada actividad sí trae schema.org/Event. Estas
pruebas cubren las dos mitades: encontrar los enlaces de ficha en el listado y
sacar el evento de la ficha, incluso cuando está escrita en prosa.
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.models import DateWindow  # noqa: E402
from eventos.sources.feeds import FichasSource  # noqa: E402

VENTANA = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 30))

LISTADO = """
<html><body>
  <nav><a href="/">Inicio</a><a href="/contacto">Contacto</a></nav>
  <a href="/agenda/concierto-de-camara">Concierto de cámara</a>
  <a href="/agenda/muestra-de-fotografia">Muestra de fotografía</a>
  <a href="/agenda/concierto-de-camara#mapa">El mismo, con ancla</a>
  <a href="https://otrositio.com/agenda/ajeno">Otro sitio</a>
  <a href="/agenda">Volver a la agenda</a>
</body></html>
"""


def _fuente(**kwargs) -> FichasSource:
    return FichasSource("Sala X", "https://sala.ar/agenda",
                        default_venue="Sala X", **kwargs)


# --- encontrar las fichas en el listado ------------------------------------

def test_junta_las_fichas_y_descarta_el_resto():
    fichas = _fuente()._fichas(BeautifulSoup(LISTADO, "lxml"))
    assert fichas == [
        "https://sala.ar/agenda/concierto-de-camara",
        "https://sala.ar/agenda/muestra-de-fotografia",
    ]


def test_no_se_lleva_el_menu_ni_otros_dominios():
    fichas = _fuente()._fichas(BeautifulSoup(LISTADO, "lxml"))
    assert not any("otrositio.com" in f for f in fichas)
    assert "https://sala.ar/contacto" not in fichas
    # El propio listado no es una ficha de sí mismo.
    assert "https://sala.ar/agenda" not in fichas


def test_ruta_ficha_acota_cuando_las_palabras_genericas_traen_de_mas():
    fuente = _fuente(ruta_ficha="/agenda/muestra")
    assert fuente._fichas(BeautifulSoup(LISTADO, "lxml")) == [
        "https://sala.ar/agenda/muestra-de-fotografia",
    ]


# --- leer la ficha en prosa ------------------------------------------------

FICHA_EN_PROSA = """
<html><body><article>
  <h1>Concierto de cámara</h1>
  <p>El sábado 12 de septiembre a las 19:30 en la sala principal.</p>
  <p>Entrada libre y gratuita hasta agotar la capacidad.</p>
</article></body></html>
"""


def test_saca_el_evento_de_una_ficha_escrita_en_prosa():
    eventos, motivo = _fuente()._de_texto(
        BeautifulSoup(FICHA_EN_PROSA, "lxml"), {}, VENTANA,
        "https://sala.ar/agenda/concierto-de-camara")
    assert motivo == ""
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.title == "Concierto de cámara"
    assert evento.date == "2026-09-12"
    assert evento.start_time == "19:30"
    assert evento.venue.name == "Sala X"
    assert evento.access_mode == "ORDEN_DE_LLEGADA"


def test_sin_fecha_escrita_no_hay_evento():
    """La invariante: nunca se inventa una fecha a partir de hoy."""
    ficha = FICHA_EN_PROSA.replace("El sábado 12 de septiembre a las 19:30",
                                   "Próximamente")
    eventos, motivo = _fuente()._de_texto(
        BeautifulSoup(ficha, "lxml"), {}, VENTANA, "https://sala.ar/x")
    assert eventos == []
    assert motivo == "fecha"


def test_si_no_dice_que_es_gratis_no_se_publica():
    """En prosa el silencio no significa gratis: hay que exigir la palabra."""
    ficha = FICHA_EN_PROSA.replace("Entrada libre y gratuita hasta agotar la "
                                   "capacidad.", "Se recomienda llegar temprano.")
    eventos, motivo = _fuente()._de_texto(
        BeautifulSoup(ficha, "lxml"), {}, VENTANA, "https://sala.ar/x")
    assert eventos == []
    assert motivo == "precio"


def test_una_muestra_con_rango_da_un_evento_por_dia_con_id_propio():
    ficha = """
    <html><body><article>
      <h1>Muestra de fotografía</h1>
      <p>Puede visitarse del 10 al 13 de septiembre, con entrada libre.</p>
    </article></body></html>
    """
    eventos, _ = _fuente()._de_texto(
        BeautifulSoup(ficha, "lxml"), {}, VENTANA, "https://sala.ar/x")
    assert [e.date for e in eventos] == [
        "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13"]
    assert len({e.id for e in eventos}) == 4


# --- el listado completo ---------------------------------------------------

def test_un_listado_sin_fichas_no_explota(capsys):
    ses = Mock()
    ses.get.return_value = Mock(text="<html><body><p>nada</p></body></html>",
                                status_code=200, raise_for_status=Mock())
    assert _fuente().fetch(ses, VENTANA) == []
    assert "no expone enlaces a fichas" in capsys.readouterr().out
