"""Agendas de los principales centros culturales y museos públicos de CABA.

Cada clase solo declara su URL, su sede por defecto y sus selectores: toda la
lógica de extracción vive en HtmlAgendaSource. Sumar una sede nueva es
agregar una clase de seis líneas y registrarla en ALL_SOURCES.

Los selectores son un punto de partida, no algo verificado sitio por sitio:
la vía principal sigue siendo el JSON-LD schema.org, y si un sitio cambia el
maquetado solo se toca su bloque de selectores.
"""
from .html_source import HtmlAgendaSource


class CentroCulturalRecoletaSource(HtmlAgendaSource):
    name = "Centro Cultural Recoleta"
    url = "https://www.centroculturalrecoleta.org/agenda"
    default_venue = "Centro Cultural Recoleta"

    item_selector = "article, .evento, .card, .actividad"
    title_selector = "h2, h3, .titulo, .title"
    date_selector = "time, .fecha, .date"
    time_selector = ".hora, time"
    venue_selector = ".sala, .espacio"
    summary_selector = ".bajada, .excerpt, p"


class CasaBicentenarioSource(HtmlAgendaSource):
    name = "Casa Nacional del Bicentenario"
    url = "https://www.casanacionaldelbicentenario.gob.ar/agenda"
    default_venue = "Casa Nacional del Bicentenario"

    item_selector = "article, .evento, .actividad, .views-row"
    title_selector = "h2, h3, .titulo"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".sala, .sede"
    summary_selector = ".bajada, .excerpt, p"


class MuseoBellasArtesSource(HtmlAgendaSource):
    name = "Museo Nacional de Bellas Artes"
    url = "https://www.bellasartes.gob.ar/agenda/"
    default_venue = "Museo Nacional de Bellas Artes"

    item_selector = "article, .actividad, .evento, .card"
    title_selector = "h2, h3, .titulo"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".sala"
    summary_selector = ".bajada, .excerpt, p"


class ComplejoTeatralSource(HtmlAgendaSource):
    name = "Complejo Teatral de Buenos Aires"
    url = "https://complejoteatral.gob.ar/cartelera"
    default_venue = "Teatro San Martín"

    item_selector = "article, .obra, .espectaculo, .card"
    title_selector = "h2, h3, .titulo"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".teatro, .sala, .sede"
    summary_selector = ".bajada, .excerpt, p"


class CulturaNacionSource(HtmlAgendaSource):
    name = "Cultura Nación"
    url = "https://www.cultura.gob.ar/agenda/"
    default_venue = "Ciudad de Buenos Aires"

    item_selector = "article, .agenda-item, .card, .evento"
    title_selector = "h2, h3, .titulo"
    date_selector = "time, .fecha"
    time_selector = ".hora, time"
    venue_selector = ".lugar, .sede, .espacio"
    summary_selector = ".bajada, .excerpt, p"
