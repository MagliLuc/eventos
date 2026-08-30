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
