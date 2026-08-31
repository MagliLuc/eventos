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
    fichas, _ = _fuente()._fichas(BeautifulSoup(LISTADO, "lxml"))
    assert fichas == [
        "https://sala.ar/agenda/concierto-de-camara",
        "https://sala.ar/agenda/muestra-de-fotografia",
    ]


def test_no_se_lleva_el_menu_ni_otros_dominios():
    fichas, _ = _fuente()._fichas(BeautifulSoup(LISTADO, "lxml"))
    assert not any("otrositio.com" in f for f in fichas)
    assert "https://sala.ar/contacto" not in fichas
    # El propio listado no es una ficha de sí mismo.
    assert "https://sala.ar/agenda" not in fichas


def test_ruta_ficha_acota_cuando_las_palabras_genericas_traen_de_mas():
    fuente = _fuente(ruta_ficha="/agenda/muestra")
    fichas, _ = fuente._fichas(BeautifulSoup(LISTADO, "lxml"))
    assert fichas == ["https://sala.ar/agenda/muestra-de-fotografia"]


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
    assert "sin fichas ni por listado ni por sitemap" in capsys.readouterr().out


# --- la fecha en la tarjeta del listado ------------------------------------
# Caso real: el Centro Cultural Recoleta pone "Desde el jueves 20.08 | 18 h" en
# la tarjeta del listado, y la ficha solo describe la actividad. Sin leer la
# tarjeta se perdían las 27 entradas de su agenda.

LISTADO_CON_FECHA = """
<html><body>
  <div class="box-info event-info">
    <span>#Muestra</span>
    <a href="/agenda/melodia-encadenada">Melodía encadenada</a>
    <div class="more-info">Desde el jueves 20.09 | 18 h | Entrada libre</div>
  </div>
</body></html>
"""

FICHA_SIN_FECHA = """
<html><body><article>
  <h1>Melodía encadenada</h1>
  <p>Una muestra sobre el sonido y la repetición. Entrada libre y gratuita.</p>
</article></body></html>
"""


def test_la_tarjeta_del_listado_se_guarda_como_contexto():
    _, contexto = _fuente()._fichas(BeautifulSoup(LISTADO_CON_FECHA, "lxml"))
    assert "20.09" in contexto["https://sala.ar/agenda/melodia-encadenada"]


def test_si_la_ficha_no_fecha_se_usa_la_fecha_de_la_tarjeta():
    eventos, motivo = _fuente()._de_texto(
        BeautifulSoup(FICHA_SIN_FECHA, "lxml"), {}, VENTANA,
        "https://sala.ar/agenda/melodia-encadenada",
        "#Muestra Melodía encadenada Desde el jueves 20.09 | 18 h")
    assert motivo == ""
    assert [e.date for e in eventos] == ["2026-09-20"]
    assert eventos[0].start_time == "18:00"


def test_la_ficha_le_gana_a_la_tarjeta():
    """Si la ficha fecha, manda la ficha: es el dato más específico."""
    eventos, _ = _fuente()._de_texto(
        BeautifulSoup(FICHA_EN_PROSA, "lxml"), {}, VENTANA,
        "https://sala.ar/x", "Desde el jueves 20.09 | 18 h")
    assert [e.date for e in eventos] == ["2026-09-12"]


# --- casos que salieron del HTML real de cada sitio ------------------------
# Cada uno fija un fallo concreto que la corrida en CI dejó a la vista. Son
# fragmentos destilados de las fichas que el diagnóstico dejó en
# scraper/diagnostico/, no invenciones.

def _leer(html: str, tarjeta: str = ""):
    return _fuente()._de_texto(BeautifulSoup(html, "lxml"), {}, VENTANA,
                               "https://sala.ar/x", tarjeta)


def test_usina_el_titulo_puede_estar_solo_en_title():
    """Las fichas de la Usina no tienen h1: sus 10 actividades se caían."""
    eventos, motivo = _leer("""
      <html><head><title>Entre el Sonido y el Tiempo – Usina del arte</title></head>
      <body><p>Un recorrido guiado. Entrada libre y gratuita.</p>
      <div>Fechas y horarios 04/09/2026 14 h 05/09/2026 15 h</div></body></html>
    """)
    assert motivo == ""
    assert eventos[0].title == "Entre el Sonido y el Tiempo"
    assert [e.date for e in eventos] == ["2026-09-04", "2026-09-05"]


def test_el_nombre_del_sitio_no_queda_pegado_al_titulo():
    from eventos.sources.feeds import _titulo_de
    for crudo, esperado in [
        ("Historias compartidas - Museo Moderno", "Historias compartidas"),
        ("Temporada 2026 - Teatro Colón", "Temporada 2026"),
        # La cola se corta solo si es más corta que la cabeza, que es como
        # se comporta un nombre de sitio. Si no, un título que ya usa el
        # separador se partiría al medio.
        ("A + C | El detrás de escena de una muestra",
         "A + C | El detrás de escena de una muestra"),
    ]:
        sopa = BeautifulSoup(f"<html><head><title>{crudo}</title></head></html>",
                             "lxml")
        assert _titulo_de(sopa) == esperado


def test_la_gratuidad_puede_estar_al_final_de_la_ficha():
    """Recoleta pone 'Entrada Gratuita' pasados los 5.000 caracteres."""
    relleno = "Texto sobre la muestra. " * 250
    eventos, motivo = _leer(f"""
      <html><body><h1>Sala Histórica</h1>
      <p>Visita el 10 de septiembre. {relleno}</p>
      <div>Entrada Gratuita Horarios Martes a viernes 12 a 21 h</div>
      </body></html>
    """)
    assert motivo == ""
    assert [e.date for e in eventos] == ["2026-09-10"]


def test_actividad_libre_tambien_es_gratis():
    """Fundación Proa no escribe 'gratis' sino 'Actividad libre'."""
    eventos, motivo = _leer("""
      <html><body><h1>El detrás de escena</h1>
      <p>Sábado 12 de septiembre 17 h. Actividad libre.</p></body></html>
    """)
    assert motivo == ""
    assert [e.date for e in eventos] == ["2026-09-12"]


def test_lo_que_vende_entradas_se_descarta():
    """Teatro Colón: 'Comprar entradas' es la señal de que no es gratis."""
    eventos, motivo = _leer("""
      <html><body><h1>Temporada 2026</h1>
      <p>La Filarmónica inaugura el 15 de septiembre. Comprar entradas + info</p>
      </body></html>
    """)
    assert eventos == [] and motivo == "precio"


def test_se_informa_el_motivo_de_cada_ficha_que_no_rinde(capsys):
    """El contador tiene que cubrir TODOS los motivos, no una selección.

    La corrida del 31/08 reportó '0 sin fecha, 0 sin precio' en diez fichas
    que rendían cero: el motivo real era 'titulo' y no estaba contado, así que
    un fallo se leía como un éxito vacío.
    """
    sin_titulo = "<html><body><p>Cuerpo sin encabezado ni nada.</p></body></html>"
    ses = Mock()
    ses.get.return_value = Mock(text=sin_titulo, status_code=200,
                                raise_for_status=Mock())
    _fuente()._leer_fichas(ses, ["https://sala.ar/agenda/x"], VENTANA)
    assert "sin titulo legible" in capsys.readouterr().out
