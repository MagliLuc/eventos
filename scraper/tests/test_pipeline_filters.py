"""Regresion del fallo de CI del 2026-08-30.

`turismo.buenosaires.gob.ar` publica su pagina indice "Que hacer esta semana"
con marcado schema.org/Event pero sin `location`. Al caer en la sede por
defecto de la fuente entraban al feed 7 pseudo-eventos (uno por dia de la
ventana) sin direccion, sin barrio y sin coordenadas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.models import Event, Venue  # noqa: E402
from eventos.pipeline import dedupe  # noqa: E402


def _evento(titulo: str, fecha: str, venue: Venue) -> Event:
    return Event(
        title=titulo,
        category="OTROS",
        date=fecha,
        access_mode="INGRESO_LIBRE",
        venue=venue,
    )


SEDE_GENERICA = Venue(id="ciudad-de-buenos-aires", name="Ciudad de Buenos Aires")
SEDE_REAL = Venue(
    id="usina-del-arte",
    name="Usina del Arte",
    address="Caffarena 1",
    neighborhood="La Boca",
    commune=4,
    lat=-34.6390,
    lon=-58.3576,
)


def test_la_sede_generica_no_es_ubicable():
    assert not SEDE_GENERICA.is_locatable


def test_una_sede_sin_coordenadas_pero_con_barrio_si_es_ubicable():
    # Una sede nueva todavia sin geocodificar tiene que seguir publicandose:
    # aparece en la lista aunque no en el mapa.
    nueva = Venue(id="centro-cultural-nuevo", name="Centro Cultural Nuevo",
                  neighborhood="Chacarita")
    assert nueva.is_locatable


def test_se_descartan_los_pseudo_eventos_de_la_pagina_indice():
    fechas = [f"2026-09-0{d}" for d in range(1, 8)]
    basura = [_evento("Qué hacer esta semana", f, SEDE_GENERICA) for f in fechas]
    reales = [_evento("Gran Milonga de Cierre", "2026-09-01", SEDE_REAL)]

    publicados = [e for e in dedupe(basura + reales) if e.venue.is_locatable]

    assert [e.title for e in publicados] == ["Gran Milonga de Cierre"]
