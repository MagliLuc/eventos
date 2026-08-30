"""Fuente curada a mano.

Sirve para dos cosas: sembrar el JSON la primera vez y, sobre todo, para
que la app nunca quede sin datos si todas las fuentes web fallan un dia.
Se lee de `scraper/seed/*.json` y no requiere red.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from ..models import Event, Venue
from .base import Source

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


class LocalSeedSource(Source):
    name = "seed local"
    url = str(SEED_DIR)

    def fetch(self, session: requests.Session, target_date: str) -> list[Event]:
        if not SEED_DIR.exists():
            return []
        events: list[Event] = []
        for path in sorted(SEED_DIR.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for raw in payload.get("events", []):
                venue = Venue(**raw.pop("venue"))
                events.append(Event(venue=venue, **raw))
        return events
