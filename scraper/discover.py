#!/usr/bin/env python3
"""Sondea sitios de eventos buscando endpoints estructurados.

Antes de pelear con selectores CSS conviene revisar si el sitio ya expone
los datos en limpio. Este script prueba, por cada dominio:

  - WordPress REST      /wp-json/wp/v2/posts        (activa por defecto)
  - Drupal JSON:API     /jsonapi
  - CKAN                /api/3/action/package_list  (portales de datos)
  - Sitemaps            /sitemap.xml, /sitemap_index.xml
  - Feeds               /feed, /rss, /atom.xml, /events.ics
  - JSON-LD             schema.org/Event embebido en el HTML
  - SPA                 __NEXT_DATA__ / __NUXT__ / llamadas fetch visibles

Uso:
    python scraper/discover.py                      # los sitios del proyecto
    python scraper/discover.py https://otro.gob.ar  # uno puntual
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from eventos.sources import ALL_SOURCES  # noqa: E402
from eventos.sources.base import USER_AGENT, extract_jsonld_events  # noqa: E402

SONDAS = [
    ("WordPress REST", "/wp-json/wp/v2/posts?per_page=1", "json"),
    ("WordPress REST (tipo evento)", "/wp-json/wp/v2/evento?per_page=1", "json"),
    ("Drupal JSON:API", "/jsonapi", "json"),
    ("CKAN", "/api/3/action/package_list", "json"),
    ("Sitemap", "/sitemap.xml", "xml"),
    ("Sitemap index", "/sitemap_index.xml", "xml"),
    ("RSS", "/feed", "xml"),
    ("RSS alternativo", "/rss", "xml"),
]

VERDE, ROJO, GRIS, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-AR,es"})
    return s


def _probe(session, base: str, path: str, kind: str) -> tuple[bool, str]:
    url = urljoin(base, path)
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
    except Exception as exc:
        return False, f"{type(exc).__name__}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"

    body = r.text.strip()
    if kind == "json":
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return False, "responde 200 pero no es JSON"
        n = len(data) if isinstance(data, (list, dict)) else 0
        return True, f"JSON con {n} claves/items — {url}"
    if kind == "xml" and body[:5].lower().startswith(("<?xml", "<urls", "<rss")):
        return True, f"{len(body)//1024} KB — {url}"
    return False, "no parece el formato esperado"


def _inspect_page(session, url: str) -> list[str]:
    """Mira el HTML de la agenda: JSON-LD, SPA y endpoints en el código."""
    hallazgos: list[str] = []
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as exc:
        return [f"{ROJO}no responde: {type(exc).__name__}{RESET}"]

    soup = BeautifulSoup(r.text, "lxml")

    eventos = extract_jsonld_events(soup)
    if eventos:
        nombres = [e.get("name", "?") for e in eventos[:3]]
        hallazgos.append(f"{VERDE}JSON-LD: {len(eventos)} schema.org/Event{RESET} → {nombres}")

    for marca, etiqueta in (("__NEXT_DATA__", "Next.js"), ("__NUXT__", "Nuxt")):
        if marca in r.text:
            hallazgos.append(
                f"{VERDE}SPA {etiqueta} detectada{RESET} — el estado inicial viene "
                f"embebido en <script id=\"{marca}\">, se puede leer directo"
            )

    # Endpoints que la propia pagina llama: la via mas rentable.
    apis = set(re.findall(r'["\'](/(?:api|wp-json|jsonapi)/[^"\'\s?]{3,60})', r.text))
    for api in sorted(apis)[:6]:
        hallazgos.append(f"{VERDE}endpoint en el código:{RESET} {urljoin(url, api)}")

    if not hallazgos:
        n = len(soup.select("article, .evento, .card, .actividad"))
        hallazgos.append(
            f"{GRIS}sin datos estructurados; {n} nodos que parecen items "
            f"→ toca scraping por selectores{RESET}"
        )
    return hallazgos


def revisar(session, url: str) -> None:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    print(f"\n\033[1m{base}\033[0m  ({url})")

    for nombre, path, kind in SONDAS:
        ok, detalle = _probe(session, base, path, kind)
        marca = f"{VERDE}✓{RESET}" if ok else f"{GRIS}·{RESET}"
        color = "" if ok else GRIS
        print(f"  {marca} {color}{nombre:<28}{RESET} {color}{detalle}{RESET}")

    print("  — página de agenda —")
    for linea in _inspect_page(session, url):
        print(f"    {linea}")


def main() -> int:
    urls = sys.argv[1:] or [s.url for s in ALL_SOURCES if s.url.startswith("http")]
    session = _session()
    print(f"Sondeando {len(urls)} sitio(s). Verde = hay datos estructurados.")
    for url in urls:
        revisar(session, url)
    print(
        "\nSi algo salió en verde, conviene escribir una Source contra ese "
        "endpoint en vez de pelear con selectores CSS: es JSON y no se rompe "
        "con cada rediseño."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
