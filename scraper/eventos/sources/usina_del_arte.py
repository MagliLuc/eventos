"""Agenda de la Usina del Arte (Gobierno de la Ciudad, La Boca)."""
from .html_source import HtmlAgendaSource


class UsinaDelArteSource(HtmlAgendaSource):
    name = "Usina del Arte"
    url = "https://usinadelarte.ar/actividades/"
    default_venue = "Usina del Arte"

    item_selector = "article, .actividad, .evento"
    title_selector = "h2, h3, .entry-title"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".sala, .sede"
    summary_selector = ".entry-summary, .excerpt, p"
