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


def test_todas_las_sedes_tienen_coordenadas(payload):
    sin_coords = [
        e["id"] for e in payload["events"]
        if e["venue"].get("lat") is None or e["venue"].get("lon") is None
    ]
    assert not sin_coords, f"sedes sin geolocalizar: {sin_coords}"
