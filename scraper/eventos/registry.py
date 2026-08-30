"""Carga las fuentes desde `scraper/sources.json`.

Separar el *qué* se consulta (datos) del *cómo* se consulta (código) permite
agregar una fuente sin tocar Python, y —más importante— deja que
`discover.py` promueva candidatos a activos con evidencia en vez de que
alguien adivine.
"""
from __future__ import annotations

import json
from pathlib import Path

from .sources.ba_data import BaDataSource
from .sources.base import Source
from .sources.feeds import IcsSource, RssSource, TribeEventsSource
from .sources.html_source import HtmlAgendaSource

REGISTRO = Path(__file__).resolve().parent.parent / "sources.json"


class _AgendaConfigurable(HtmlAgendaSource):
    """HtmlAgendaSource armada desde el registro (JSON-LD + selectores)."""

    def __init__(self, name: str, url: str, default_venue: str = "",
                 selectors: dict | None = None):
        self.name, self.url, self.default_venue = name, url, default_venue
        for clave, valor in (selectors or {}).items():
            # Solo se permiten los selectores declarados en la clase base:
            # el registro no puede inyectar atributos arbitrarios.
            atributo = f"{clave}_selector"
            if hasattr(HtmlAgendaSource, atributo):
                setattr(self, atributo, valor)


def _construir(entrada: dict) -> Source | None:
    kind = entrada.get("kind")
    nombre = entrada.get("name") or "sin nombre"
    url = entrada.get("url") or ""
    sede = entrada.get("venue", "")

    if kind == "ckan":
        return BaDataSource()
    if not url:
        print(f"  [registro] '{nombre}' no tiene URL; se saltea")
        return None
    if kind == "ics":
        return IcsSource(nombre, url, sede)
    if kind == "tribe":
        return TribeEventsSource(nombre, url, sede)
    if kind == "rss":
        return RssSource(nombre, url, sede)
    if kind in ("jsonld", "css"):
        return _AgendaConfigurable(nombre, url, sede, entrada.get("selectors"))

    print(f"  [registro] '{nombre}' usa un kind desconocido: {kind!r}")
    return None


def cargar(ruta: Path = REGISTRO, incluir: tuple[str, ...] = ("activo",)) -> list[Source]:
    """Fuentes del registro con alguno de los `status` pedidos."""
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    fuentes: list[Source] = []
    for entrada in datos.get("sources", []):
        if entrada.get("status") not in incluir:
            continue
        fuente = _construir(entrada)
        if fuente is not None:
            fuentes.append(fuente)
    return fuentes


def candidatos(ruta: Path = REGISTRO) -> list[dict]:
    """Entradas a sondear con discover.py (candidatos y bloqueadas)."""
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return [e for e in datos.get("sources", [])
            if e.get("status") in ("candidato", "bloqueado") and e.get("url")]
