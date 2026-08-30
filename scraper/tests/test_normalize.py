"""Tests del normalizador. Corren sin red: `python -m pytest scraper/tests`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.normalize import (  # noqa: E402
    detect_access_mode,
    detect_category,
    is_free,
    parse_times,
)
from eventos.models import Event, Venue  # noqa: E402
from eventos.pipeline import dedupe, validate  # noqa: E402
from eventos.venues import build_venue, canonical_id  # noqa: E402


def test_detect_category_prioriza_infantiles():
    assert detect_category("Concierto para chicos", "musica en familia") == "INFANTILES"


def test_detect_category_por_disciplina():
    assert detect_category("Muestra de pintura contemporánea") == "ARTES_VISUALES"
    assert detect_category("Ciclo de cortometrajes") == "CINE"
    assert detect_category("Gran milonga de cierre") == "MUSICA"
    assert detect_category("Feria de artesanías criollas") == "FERIAS"
    assert detect_category("Compañía Nacional de Danza") == "TEATRO"
    assert detect_category("Actividad sin pistas") == "OTROS"


def test_detect_access_mode():
    assert detect_access_mode("Requiere reserva previa") == "RESERVA_PREVIA"
    assert detect_access_mode("Por orden de llegada hasta agotar capacidad") == "ORDEN_DE_LLEGADA"
    assert detect_access_mode("Ingreso libre y gratuito") == "INGRESO_LIBRE"


def test_parse_times_rango_y_simple():
    assert parse_times("de 14:00 a 17:00 h") == ("14:00", "17:00")
    assert parse_times("19:30 hs") == ("19:30", None)
    assert parse_times("Desde las 11 hs") == ("11:00", None)
    assert parse_times("sin horario") == (None, None)


def test_parse_times_descarta_horas_invalidas():
    assert parse_times("36:99") == (None, None)


def test_is_free():
    assert is_free("Entrada libre y gratuita")
    assert not is_free("Entrada general $ 12.000")
    assert is_free("Muestra permanente")  # sin marcas de pago -> se asume libre


def test_canonical_id_resuelve_alias_y_salas():
    assert canonical_id("CCK") == "palacio-libertad"
    assert canonical_id("Palacio Libertad · Auditorio 513") == "palacio-libertad"
    assert canonical_id("Usina del Arte - Sala de Cámara") == "usina-del-arte"


def test_build_venue_completa_coordenadas():
    venue = build_venue("Usina del Arte")
    assert venue.commune == 4
    assert venue.neighborhood == "La Boca"
    assert venue.lat is not None and venue.lon is not None


def _event(**kwargs):
    base = dict(
        title="Milonga",
        category="MUSICA",
        date="2030-01-01",
        access_mode="INGRESO_LIBRE",
        venue=Venue(id="usina-del-arte", name="Usina del Arte"),
    )
    base.update(kwargs)
    return Event(**base)


def test_id_estable_entre_corridas():
    assert _event().id == _event().id


def test_dedupe_conserva_la_version_mas_completa():
    pobre = _event()
    rica = _event(description="Con orquesta en vivo", start_time="17:00")
    result = dedupe([pobre, rica])
    assert len(result) == 1
    assert result[0].description == "Con orquesta en vivo"


def test_validate_detecta_categoria_invalida():
    problems = validate([_event(category="ROCK")])
    assert any("categoria invalida" in p for p in problems)
