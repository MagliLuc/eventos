"""Valida docs/events.json contra el JSON Schema publicado."""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scraper"))


@pytest.fixture(scope="module")
def schema():
    return json.loads((ROOT / "docs" / "events.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def payload():
    return json.loads((ROOT / "docs" / "events.json").read_text(encoding="utf-8"))


def test_events_json_cumple_el_schema(schema, payload):
    jsonschema.validate(payload, schema)


def test_ids_unicos(payload):
    ids = [e["id"] for e in payload["events"]]
    assert len(ids) == len(set(ids))


def test_todos_los_eventos_tienen_sede_ubicable(payload):
    """Sin lugar no hay evento: no se podria mapear ni abrir en la app de mapas.

    Este es el invariante duro. Exigir coordenadas a todos seria mas
    estricto de lo necesario: una sede nueva todavia no geocodificada se
    muestra igual en la lista, solo no aparece en el mapa.
    """
    sin_lugar = [
        e["id"] for e in payload["events"]
        if not (
            (e["venue"].get("lat") is not None and e["venue"].get("lon") is not None)
            or e["venue"].get("address")
            or e["venue"].get("neighborhood")
        )
    ]
    assert not sin_lugar, f"eventos sin sede ubicable: {sin_lugar}"


def test_cobertura_de_coordenadas(payload):
    """Umbral de calidad: detecta que el catalogo de sedes quedo atras.

    Falla si el mapa se vaciaria, sin romper la corrida porque apareciera
    una sede nueva.
    """
    eventos = payload["events"]
    if not eventos:
        return
    con_coords = [
        e for e in eventos
        if e["venue"].get("lat") is not None and e["venue"].get("lon") is not None
    ]
    cobertura = len(con_coords) / len(eventos)
    sin_coords = sorted({
        e["venue"]["name"] for e in eventos if e["venue"].get("lat") is None
    })
    assert cobertura >= 0.7, (
        f"solo {cobertura:.0%} de los eventos tiene coordenadas. "
        f"Sedes a agregar en venues.KNOWN_VENUES: {sin_coords}"
    )


# --- sedes: una fuente activa sin entrada en el catalogo tira sus eventos ---

def test_toda_fuente_activa_resuelve_a_una_sede_ubicable():
    """Museo Moderno perdió sus 40 eventos por faltar en KNOWN_VENUES.

    `build_venue` devolvía una sede sin dirección ni barrio, `is_locatable` la
    rechazaba y el pipeline los descartaba en silencio — el log sólo decía
    "Descartados 50 eventos sin sede ubicable", sin nombrar la causa.

    Se exceptúa el marcador genérico de las fuentes que agregan varias sedes:
    ahí la sede real viene en el JSON-LD de cada ficha, y una que no la traiga
    debe descartarse.
    """
    import json
    from eventos.venues import build_venue

    GENERICAS = {"Ciudad de Buenos Aires"}
    registro = json.loads((ROOT / "scraper" / "sources.json").read_text(encoding="utf-8"))

    sin_sede = []
    for fuente in registro["sources"]:
        sede = fuente.get("venue")
        if fuente.get("status") != "activo" or not sede or sede in GENERICAS:
            continue
        if not build_venue(sede).is_locatable:
            sin_sede.append(f"{fuente['name']} -> {sede!r}")

    assert not sin_sede, (
        "Estas fuentes activas resuelven a una sede que no se puede ubicar, "
        "así que el pipeline va a descartar todos sus eventos. Agregarlas a "
        "KNOWN_VENUES en eventos/venues.py:\n  " + "\n  ".join(sin_sede))
