"""Agenda del Palacio Libertad (ex CCK). Casi todo su ciclo es gratuito."""
from .html_source import HtmlAgendaSource


class PalacioLibertadSource(HtmlAgendaSource):
    name = "Palacio Libertad"
    url = "https://palaciolibertad.gob.ar/agenda/"
    default_venue = "Palacio Libertad"

    item_selector = "article, .agenda-item, .card-evento"
    title_selector = "h2, h3, .titulo"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".sala, .espacio, .sede"
    summary_selector = ".bajada, .excerpt, p"
