"""Agenda de eventos del sitio oficial de turismo de la Ciudad."""
from .html_source import HtmlAgendaSource


class BuenosAiresTurismoSource(HtmlAgendaSource):
    name = "Turismo Buenos Aires"
    url = "https://turismo.buenosaires.gob.ar/es/eventos"
    default_venue = "Ciudad de Buenos Aires"

    item_selector = ".event-item, article, .views-row"
    title_selector = "h2, h3, .event-title"
    date_selector = "time, .date-display-single, .fecha"
    time_selector = ".hora, .field--name-field-hora, time"
    venue_selector = ".field--name-field-lugar, .lugar, .venue"
    summary_selector = ".field--name-body, .summary, p"
