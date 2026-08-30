#!/usr/bin/env python3
"""Sondea sitios de eventos y emite la configuración de las fuentes que sirven.

Este script existe porque quien escribe el scraper casi nunca puede probar los
sitios objetivo (red bloqueada, geo-restricciones, WAF). En vez de adivinar
selectores, se corre esto desde una red con acceso real y se pega en
`scraper/sources.json` lo que imprime al final.

Prueba, por cada sitio y en orden de calidad de dato:

  1. ICS        /events.ics, /?ical=1, /agenda.ics, /calendario.ics
  2. Tribe      /wp-json/tribe/events/v1/events   (The Events Calendar)
  3. JSON-LD    schema.org/Event embebido en la página
  4. WP posts   /wp-json/wp/v2/posts              (artículos, no eventos)
  5. RSS/Atom   /feed, /rss, /atom.xml, /feed/atom
  6. CKAN       /api/3/action/package_list
  7. SPA        __NEXT_DATA__ / __NUXT__ y endpoints en el código
  8. Selectores conteo de nodos que parecen items

Uso:
    python scraper/discover.py                    # candidatos de sources.json
    python scraper/discover.py https://sitio.ar   # uno puntual
    python scraper/discover.py --todos            # incluye los ya activos
    python scraper/discover.py --compacto         # una línea por sitio (para CI)
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

from eventos.registry import candidatos, cargar  # noqa: E402
from eventos.sources.base import BROWSER_HEADERS, extract_jsonld_events  # noqa: E402
from eventos.sources.feeds import parse_feed, parse_ics  # noqa: E402

VERDE, AMARILLO, ROJO, GRIS, FIN = (
    "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m")

RUTAS_ICS = ("/events.ics", "/?ical=1", "/agenda.ics", "/calendario.ics")
RUTAS_FEED = ("/feed", "/rss", "/feed/atom", "/atom.xml", "/index.xml")
RUTA_TRIBE = "/wp-json/tribe/events/v1/events"
RUTA_WP = "/wp-json/wp/v2/posts?per_page=1"
RUTA_CKAN = "/api/3/action/package_list"


def sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    return s


def _get(ses, url: str, timeout: int = 20):
    try:
        return ses.get(url, timeout=timeout, allow_redirects=True)
    except Exception as exc:
        return exc


def _base(url: str) -> str:
    partes = urlparse(url)
    return f"{partes.scheme}://{partes.netloc}"


# --- sondas -----------------------------------------------------------------

def probar_ics(ses, base: str) -> tuple[str, dict] | None:
    for ruta in RUTAS_ICS:
        url = urljoin(base, ruta)
        r = _get(ses, url)
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        eventos = parse_ics(r.text)
        if eventos:
            return f"{len(eventos)} VEVENT", {"kind": "ics", "url": url}
    return None


def probar_tribe(ses, base: str) -> tuple[str, dict] | None:
    url = urljoin(base, RUTA_TRIBE)
    r = _get(ses, url)
    if isinstance(r, Exception) or r.status_code != 200:
        return None
    try:
        datos = r.json()
    except ValueError:
        return None
    eventos = datos.get("events")
    if isinstance(eventos, list):
        gratis = sum(1 for e in eventos
                     if not str(e.get("cost") or "").strip()
                     or re.fullmatch(r"0([.,]0+)?|gratis|free", str(e.get("cost")), re.I))
        return (f"{len(eventos)} eventos ({gratis} sin costo)",
                {"kind": "tribe", "url": url})
    return None


def probar_jsonld(ses, url: str) -> tuple[str, dict] | None:
    r = _get(ses, url, timeout=30)
    if isinstance(r, Exception) or r.status_code != 200:
        return None
    sopa = BeautifulSoup(r.text, "lxml")
    eventos = extract_jsonld_events(sopa)
    if eventos:
        nombres = [e.get("name", "?") for e in eventos[:2]]
        return f"{len(eventos)} schema.org/Event → {nombres}", {"kind": "jsonld", "url": url}
    return None


def probar_feed(ses, base: str) -> tuple[str, dict] | None:
    for ruta in RUTAS_FEED:
        url = urljoin(base, ruta)
        r = _get(ses, url)
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        entradas = parse_feed(r.text)
        if entradas:
            return f"{len(entradas)} entradas", {"kind": "rss", "url": url}
    return None


def probar_wp(ses, base: str) -> str | None:
    r = _get(ses, urljoin(base, RUTA_WP))
    if isinstance(r, Exception) or r.status_code != 200:
        return None
    try:
        datos = r.json()
    except ValueError:
        return None
    return f"{len(datos)} post(s)" if isinstance(datos, list) else None


def probar_ckan(ses, base: str) -> str | None:
    r = _get(ses, urljoin(base, RUTA_CKAN))
    if isinstance(r, Exception) or r.status_code != 200:
        return None
    try:
        datos = r.json()
    except ValueError:
        return None
    nombres = datos.get("result") or []
    return f"{len(nombres)} datasets" if nombres else None


def inspeccionar_pagina(ses, url: str) -> list[str]:
    """SPA, endpoints internos y densidad de nodos: pistas de último recurso."""
    pistas: list[str] = []
    r = _get(ses, url, timeout=30)
    if isinstance(r, Exception):
        return [f"{ROJO}no responde: {type(r).__name__}{FIN}"]
    if r.status_code != 200:
        pistas.append(f"{ROJO}HTTP {r.status_code}{FIN}"
                      + (f"  {AMARILLO}← probable bloqueo por IP o WAF{FIN}"
                         if r.status_code in (403, 429) else ""))
        return pistas

    for marca, etiqueta in (("__NEXT_DATA__", "Next.js"), ("__NUXT__", "Nuxt")):
        if marca in r.text:
            pistas.append(f"{VERDE}SPA {etiqueta}{FIN}: el estado inicial está en "
                          f'<script id="{marca}">, se lee directo')

    apis = sorted(set(re.findall(
        r'["\'](/(?:api|wp-json|jsonapi|graphql)/[^"\'\s?]{3,60})', r.text)))
    for api in apis[:6]:
        pistas.append(f"{VERDE}endpoint en el código{FIN}: {urljoin(url, api)}")

    if not pistas:
        sopa = BeautifulSoup(r.text, "lxml")
        n = len(sopa.select("article, .evento, .card, .actividad, .event"))
        pistas.append(f"{GRIS}sin datos estructurados; {n} nodos tipo item "
                      f"→ haría falta scraping por selectores{FIN}")
    return pistas


# --- orquestación -----------------------------------------------------------

def revisar(ses, entrada: dict) -> dict | None:
    url = entrada["url"]
    nombre = entrada.get("name", url)
    base = _base(url)
    print(f"\n\033[1m{nombre}\033[0m  {GRIS}{url}{FIN}")

    for etiqueta, sonda in (
        ("ICS (calendario)", lambda: probar_ics(ses, base)),
        ("Tribe / The Events Calendar", lambda: probar_tribe(ses, base)),
        ("JSON-LD schema.org/Event", lambda: probar_jsonld(ses, url)),
        ("RSS / Atom", lambda: probar_feed(ses, base)),
    ):
        resultado = sonda()
        if resultado:
            detalle, config = resultado
            print(f"  {VERDE}✓ {etiqueta:<28}{FIN} {detalle}")
            propuesta = {
                "name": entrada.get("name", nombre),
                "kind": config["kind"],
                "url": config["url"],
                "venue": entrada.get("venue", ""),
                "status": "activo",
            }
            print(f"  {VERDE}→ usar este mecanismo{FIN}")
            return propuesta
        print(f"  {GRIS}· {etiqueta:<28} no{FIN}")

    for etiqueta, sonda in (("WordPress REST", lambda: probar_wp(ses, base)),
                            ("CKAN", lambda: probar_ckan(ses, base))):
        detalle = sonda()
        marca = f"{AMARILLO}~{FIN}" if detalle else f"{GRIS}·{FIN}"
        print(f"  {marca} {etiqueta:<28} {detalle or 'no'}")

    print(f"  {GRIS}— página —{FIN}")
    for pista in inspeccionar_pagina(ses, url):
        print(f"    {pista}")
    return None


def revisar_compacto(ses, entrada: dict) -> dict | None:
    """Una línea por sitio. Para leer el resultado desde el log de CI."""
    url, nombre, base = entrada["url"], entrada.get("name", "?"), _base(entrada["url"])

    for etiqueta, sonda in (
        ("ics", lambda: probar_ics(ses, base)),
        ("tribe", lambda: probar_tribe(ses, base)),
        ("jsonld", lambda: probar_jsonld(ses, url)),
        ("rss", lambda: probar_feed(ses, base)),
    ):
        resultado = sonda()
        if resultado:
            detalle, config = resultado
            print(f"  OK   {nombre:<34} {etiqueta:<7} {detalle}")
            return {"name": nombre, "kind": config["kind"], "url": config["url"],
                    "venue": entrada.get("venue", ""), "status": "activo"}

    # Sin mecanismo estructurado: al menos dejar dicho POR QUE.
    r = _get(ses, url, timeout=30)
    if isinstance(r, Exception):
        motivo = f"red: {type(r).__name__}"
    elif r.status_code != 200:
        motivo = f"HTTP {r.status_code}"
    else:
        extras = []
        if probar_wp(ses, base):
            extras.append("tiene wp-json/posts")
        if probar_ckan(ses, base):
            extras.append("tiene CKAN")
        for marca, etiqueta in (("__NEXT_DATA__", "Next.js"), ("__NUXT__", "Nuxt")):
            if marca in r.text:
                extras.append(f"SPA {etiqueta}")
        apis = sorted(set(re.findall(
            r'["\'](/(?:api|wp-json|jsonapi|graphql)/[^"\'\s?]{3,60})', r.text)))
        if apis:
            extras.append("endpoints: " + ", ".join(apis[:3]))
        motivo = "200 sin marcado" + (" — " + "; ".join(extras) if extras else "")
    print(f"  --   {nombre:<34} {'':<7} {motivo}")
    return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    todos = "--todos" in sys.argv
    compacto = "--compacto" in sys.argv

    if args:
        entradas = [{"name": u, "url": u} for u in args]
    else:
        entradas = candidatos()
        if todos:
            entradas += [{"name": f.name, "url": f.url} for f in cargar()]

    ses = sesion()
    if compacto:
        print(f"### PROSPECCION: {len(entradas)} sitio(s) ###")
        propuestas = [p for e in entradas if (p := revisar_compacto(ses, e))]
    else:
        print(f"Sondeando {len(entradas)} sitio(s). "
              f"{VERDE}Verde{FIN} = mecanismo utilizable.")
        propuestas = [p for e in entradas if (p := revisar(ses, e))]

    print("\n" + "=" * 70)
    if propuestas:
        print(f"{VERDE}{len(propuestas)} fuente(s) utilizable(s).{FIN} "
              f"Pegá esto en la lista `sources` de scraper/sources.json:\n")
        print(json.dumps(propuestas, ensure_ascii=False, indent=2))
    else:
        print(f"{AMARILLO}Ninguna expuso un mecanismo estructurado.{FIN}")
        print("Si viste muchos HTTP 403, corré esto desde otra red: sería\n"
              "bloqueo por IP y no algo que se arregle en el código.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
