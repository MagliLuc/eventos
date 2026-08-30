"""Regresion del fallo de CI del 2026-08-30.

`turismo.buenosaires.gob.ar` publica su pagina indice "Que hacer esta semana"
con marcado schema.org/Event pero sin `location`. Al caer en la sede por
defecto de la fuente entraban al feed 7 pseudo-eventos (uno por dia de la
ventana) sin direccion, sin barrio y sin coordenadas.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.models import DateWindow, Event, Venue  # noqa: E402
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


def test_la_ventana_rechaza_fechas_fuera_de_rango_e_invalidas():
    ventana = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 7))
    assert ventana.contains("2026-09-01")
    assert ventana.contains("2026-09-07T20:00:00-03:00")
    assert not ventana.contains("2026-08-31")
    assert not ventana.contains("2026-09-08")
    assert not ventana.contains("08/09/2026")   # no es ISO
    assert not ventana.contains(None)


# --- BA Data: parseo de CSV ------------------------------------------------
# La corrida del 2026-08-30 mostró que los datasets del portal publican CSV
# para descarga y no están cargados al datastore, así que este camino es el
# que realmente trae los datos.

def _csv_falso(contenido: str):
    from unittest.mock import Mock
    sesion = Mock()
    sesion.get.return_value = Mock(
        content=contenido.encode("utf-8"), raise_for_status=Mock()
    )
    return sesion


def test_csv_con_bom_y_separador_coma():
    from eventos.sources.ba_data import BaDataSource
    filas = BaDataSource()._csv(
        _csv_falso('﻿titulo,fecha\nMilonga,2026-09-05\n'), "http://x/y.csv"
    )
    assert filas == [{"titulo": "Milonga", "fecha": "2026-09-05"}]


def test_csv_con_separador_punto_y_coma():
    from eventos.sources.ba_data import BaDataSource
    filas = BaDataSource()._csv(
        _csv_falso('titulo;fecha\nConcierto;2026-09-06\n'), "http://x/y.csv"
    )
    assert filas == [{"titulo": "Concierto", "fecha": "2026-09-06"}]


def test_una_fila_del_csv_se_mapea_a_evento():
    from eventos.models import DateWindow
    from eventos.sources.ba_data import BaDataSource
    ventana = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 30))
    evento = BaDataSource()._to_event(
        {
            "titulo": "Concierto en el Colón",
            "fecha": "05/09/2026",          # formato dd/mm/aaaa
            "hora": "20:00",
            "sede": "Teatro Colón",
            "precio": "gratis",
        },
        ventana,
    )
    assert evento is not None
    assert evento.date == "2026-09-05"
    assert evento.start_time == "20:00"
    assert evento.venue.neighborhood == "San Nicolás"   # del catálogo local


def test_una_fila_paga_no_entra():
    from eventos.models import DateWindow
    from eventos.sources.ba_data import BaDataSource
    ventana = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 30))
    evento = BaDataSource()._to_event(
        {"titulo": "Ópera", "fecha": "05/09/2026", "precio": "$ 25.000"}, ventana
    )
    assert evento is None
