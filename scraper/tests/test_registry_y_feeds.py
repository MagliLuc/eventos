"""Registro de fuentes y extractores por mecanismo."""
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.models import DateWindow  # noqa: E402
from eventos.registry import cargar, candidatos  # noqa: E402
from eventos.sources.feeds import (  # noqa: E402
    IcsSource,
    RssSource,
    TribeEventsSource,
    parse_feed,
    parse_ics,
)

VENTANA = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 30))


def _respuesta(texto: str = "", datos=None):
    ses = Mock()
    ses.get.return_value = Mock(
        text=texto, json=Mock(return_value=datos), raise_for_status=Mock(),
        status_code=200,
    )
    return ses


# --- registro --------------------------------------------------------------

def test_el_registro_carga_solo_las_activas():
    activas = cargar()
    assert activas, "debería haber al menos una fuente activa"
    # Ninguna bloqueada puede colarse: son las que dan 403.
    nombres = {f.name for f in activas}
    assert "Palacio Libertad" not in nombres


def test_las_candidatas_no_se_consultan_pero_se_sondean():
    nombres_activos = {f.name for f in cargar()}
    for entrada in candidatos():
        assert entrada["name"] not in nombres_activos


def test_una_entrada_sin_url_no_rompe_la_carga():
    ruta = Path(__file__).parent / "_tmp_sources.json"
    ruta.write_text(json.dumps({"sources": [
        {"name": "Sin URL", "kind": "rss", "url": "", "status": "activo"},
        {"name": "Con URL", "kind": "rss", "url": "http://x/feed", "status": "activo"},
    ]}), encoding="utf-8")
    try:
        assert [f.name for f in cargar(ruta)] == ["Con URL"]
    finally:
        ruta.unlink()


def test_un_kind_desconocido_se_ignora_sin_explotar():
    ruta = Path(__file__).parent / "_tmp_kind.json"
    ruta.write_text(json.dumps({"sources": [
        {"name": "Raro", "kind": "telepatia", "url": "http://x", "status": "activo"},
    ]}), encoding="utf-8")
    try:
        assert cargar(ruta) == []
    finally:
        ruta.unlink()


# --- ICS -------------------------------------------------------------------

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Concierto al aire libre
DTSTART;TZID=America/Argentina/Buenos_Aires:20260905T200000
DTEND:20260905T220000
LOCATION:Usina del Arte
DESCRIPTION:Entrada libre y gratuita
END:VEVENT
BEGIN:VEVENT
SUMMARY:Fuera de ventana
DTSTART:20261225T200000
LOCATION:Usina del Arte
END:VEVENT
END:VCALENDAR"""


def test_ics_toma_lo_de_la_ventana_y_descarta_el_resto():
    eventos = IcsSource("Test", "http://x/e.ics").fetch(_respuesta(ICS), VENTANA)
    assert [e.title for e in eventos] == ["Concierto al aire libre"]
    ev = eventos[0]
    assert (ev.date, ev.start_time, ev.end_time) == ("2026-09-05", "20:00", "22:00")
    assert ev.venue.neighborhood == "La Boca"   # resuelto por el catálogo


def test_ics_soporta_lineas_plegadas():
    plegado = ("BEGIN:VEVENT\r\nSUMMARY:Titulo muy\r\n  largo\r\n"
               "DTSTART:20260905\r\nEND:VEVENT")
    assert parse_ics(plegado)[0]["SUMMARY"] == "Titulo muy largo"


# --- Tribe / The Events Calendar -------------------------------------------

def test_tribe_mapea_evento_gratuito():
    datos = {"events": [{
        "title": "Ciclo de cine",
        "start_date": "2026-09-10 19:00:00",
        "end_date": "2026-09-10 21:00:00",
        "cost": "0",
        "description": "<p>Entrada libre</p>",
        "venue": {"venue": "Usina del Arte", "address": "Caffarena 1"},
        "url": "http://x/evento",
    }]}
    eventos = TribeEventsSource("T", "http://x/wp-json/tribe/events/v1/events").fetch(
        _respuesta(datos=datos), VENTANA)
    assert len(eventos) == 1
    assert eventos[0].date == "2026-09-10"
    assert eventos[0].start_time == "19:00"
    assert "<p>" not in (eventos[0].description or "")   # el HTML se limpia


def test_tribe_descarta_lo_pago_por_el_campo_cost():
    datos = {"events": [{
        "title": "Ópera", "start_date": "2026-09-10 19:00:00",
        "cost": "25000", "venue": {"venue": "Teatro Colón"},
    }]}
    eventos = TribeEventsSource("T", "http://x").fetch(_respuesta(datos=datos), VENTANA)
    assert eventos == []


# --- RSS -------------------------------------------------------------------

def test_parse_feed_entiende_rss_y_atom():
    rss = ('<rss><channel><item><title>Nota</title><link>http://x/1</link>'
           '<description>d</description></item></channel></rss>')
    assert parse_feed(rss)[0]["title"] == "Nota"

    atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Nota A</title>'
            '<link href="http://x/2"/><summary>s</summary></entry></feed>')
    entrada = parse_feed(atom)[0]
    assert entrada["title"] == "Nota A" and entrada["link"] == "http://x/2"


def test_un_feed_que_no_es_xml_no_explota():
    assert parse_feed("<html>no soy un feed</html>") == []
    assert RssSource("R", "http://x/feed").fetch(_respuesta("no xml"), VENTANA) == []
