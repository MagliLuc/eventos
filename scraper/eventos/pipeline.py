"""Orquestacion: correr fuentes, deduplicar, validar y escribir events.json."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

from .models import BUENOS_AIRES, SCHEMA_VERSION, Event, now_ba_iso, today_ba
from .sources import ALL_SOURCES, LocalSeedSource, http_session
from .sources.base import Source

def dedupe(events: Iterable[Event]) -> list[Event]:
    """Un evento suele aparecer en varias agendas: gana el mas completo.

    'Mas completo' = mas campos no vacios, para no perder la descripcion o
    las coordenadas por quedarnos con la version pobre de otra fuente.
    """
    best: dict[str, Event] = {}
    for event in events:
        current = best.get(event.id)
        if current is None or _richness(event) > _richness(current):
            best[event.id] = event
    return sorted(
        best.values(),
        key=lambda e: (e.date, e.start_time or "99:99", e.title),
    )


def _richness(event: Event) -> int:
    fields = (
        event.description,
        event.start_time,
        event.end_time,
        event.venue.lat,
        event.venue.address,
        event.venue.neighborhood,
        event.image_url,
        event.reservation_url,
    )
    return sum(1 for value in fields if value not in (None, ""))


def validate(events: list[Event]) -> list[str]:
    """Chequeos baratos previos a publicar. Devuelve la lista de problemas."""
    from .models import ACCESS_MODES, CATEGORIES

    problems: list[str] = []
    seen: set[str] = set()
    for event in events:
        if event.id in seen:
            problems.append(f"id duplicado: {event.id}")
        seen.add(event.id)
        if event.category not in CATEGORIES:
            problems.append(f"{event.id}: categoria invalida {event.category!r}")
        if event.access_mode not in ACCESS_MODES:
            problems.append(f"{event.id}: modalidad invalida {event.access_mode!r}")
        try:
            date.fromisoformat(event.date)
        except ValueError:
            problems.append(f"{event.id}: fecha invalida {event.date!r}")
        if not event.title.strip():
            problems.append(f"{event.id}: titulo vacio")
    return problems


def run(
    output: Path,
    days: int = 7,
    sources: Optional[list[Source]] = None,
    include_seed: bool = True,
    keep_existing: bool = True,
) -> dict:
    """Corre el pipeline completo y escribe el JSON que consume la app."""
    sources = ALL_SOURCES if sources is None else sources
    session = http_session()
    today = today_ba()
    targets = [(today + timedelta(days=i)).isoformat() for i in range(days)]

    collected: list[Event] = []
    for source in sources:
        for target in targets:
            collected.extend(source.safe_fetch(session, target))

    if include_seed:
        collected.extend(LocalSeedSource().safe_fetch(session, today.isoformat()))

    # Red de seguridad: si hoy no scrapeamos nada (sitio caido, cambio de
    # maquetado), conservamos el JSON anterior en vez de publicar un archivo
    # vacio que dejaria la app en blanco.
    if keep_existing and output.exists():
        collected.extend(_read_existing(output))

    deduped = [e for e in dedupe(collected) if e.date >= today.isoformat()]

    # Filtro final: sin sede ubicable el evento no se puede mostrar en el
    # mapa ni abrir en la app de mapas, asi que no llega al feed.
    events = [e for e in deduped if e.venue.is_locatable]
    descartados = len(deduped) - len(events)
    if descartados:
        print(f"  Descartados {descartados} eventos sin sede ubicable.")

    problems = validate(events)
    if problems:
        raise ValueError("JSON invalido:\n  - " + "\n  - ".join(problems))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_ba_iso(),
        "city": "Ciudad Autónoma de Buenos Aires",
        "license": "Datos públicos recopilados de agendas oficiales. Uso informativo.",
        "events": [e.to_dict() for e in events],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def _read_existing(path: Path) -> list[Event]:
    from .models import Venue

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    events: list[Event] = []
    for raw in payload.get("events", []):
        raw = dict(raw)
        venue_data = raw.pop("venue", None)
        if not venue_data:
            continue
        try:
            events.append(Event(venue=Venue(**venue_data), **raw))
        except TypeError:
            continue  # campo desconocido de un schema viejo: se descarta
    return events
