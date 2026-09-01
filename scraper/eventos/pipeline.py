"""Orquestacion: correr fuentes, deduplicar, validar y escribir events.json."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from .models import (
    BUENOS_AIRES,
    SCHEMA_VERSION,
    DateWindow,
    Event,
    now_ba_iso,
    today_ba,
)
from .informe import ERROR, INCOMPLETA, InformeFuente
from .registry import cargar as cargar_fuentes
from .sources import LocalSeedSource, http_session
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
    sources = cargar_fuentes() if sources is None else sources
    session = http_session()
    today = today_ba()
    window = DateWindow.upcoming(days)
    print(f"Ventana: {window}")

    collected: list[Event] = []
    informes: list[InformeFuente] = []
    a_correr = list(sources) + ([LocalSeedSource()] if include_seed else [])
    for source in a_correr:
        # Una sola llamada por fuente: la ventana entera va como parametro.
        eventos, informe = source.fetch_con_informe(session, window)
        # El id se estampa aca y no en cada fuente: es una sola linea y evita
        # que una fuente nueva se olvide de ponerlo y quede fuera del panel.
        for evento in eventos:
            evento.source_id = source.id
        collected.extend(eventos)
        informes.append(informe)

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

    # Nunca publicar un feed vacio. Preferimos dejar el archivo anterior
    # tal cual y que la corrida quede en rojo: un JSON con cero eventos
    # deja la web en blanco y no se distingue de "hoy no hay nada".
    if not events:
        raise ValueError(
            "El pipeline no produjo ningun evento: se conserva "
            f"{output} sin cambios. Revisar el log de las fuentes."
        )

    # Cuantos eventos de cada fuente sobrevivieron al dedupe y al filtro de
    # sede. Es lo que la app tiene que mostrar: el informe crudo dice cuantos
    # extrajo la fuente, no cuantos se terminaron publicando.
    publicados = Counter(e.source_id for e in events if e.source_id)
    for informe in informes:
        informe.eventos = publicados.get(informe.id, 0)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_ba_iso(),
        "city": "Ciudad Autónoma de Buenos Aires",
        "license": "Datos públicos recopilados de agendas oficiales. Uso informativo.",
        "sources": [i.to_dict() for i in informes],
        "events": [e.to_dict() for e in events],
    }
    _resumir(informes)
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


def _resumir(informes: list[InformeFuente]) -> None:
    """Resumen legible al final de la corrida.

    Va despues del detalle de cada fuente porque en un log de 200 lineas el
    estado de las fuentes es lo primero que uno quiere ver, y buscarlo linea
    por linea es como se nos paso mas de un fallo silencioso.
    """
    print("\nEstado de las fuentes:")
    for informe in sorted(informes, key=lambda i: (i.estado != ERROR, i.nombre)):
        marca = "!!" if informe.estado in (ERROR, INCOMPLETA) else "  "
        print(f"  {marca} {informe.nombre:<32} {informe.estado:<12} {informe.detalle}")
