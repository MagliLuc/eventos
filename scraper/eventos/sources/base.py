"""Contrato comun de las fuentes y helper HTTP con reintentos."""
from __future__ import annotations

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..models import DateWindow, Event

# Cinco sitios .gob.ar devolvieron 403 al User-Agent de bot: hay un WAF que
# filtra por cabeceras. Son paginas publicas que cualquiera abre en un
# navegador, asi que mandamos las cabeceras que manda un navegador — pero
# dejando el proyecto identificado en el propio User-Agent y en `From`, para
# que quien administre el sitio sepa quienes somos y como contactarnos.
# El volumen sigue siendo un puñado de requests por dia.
CONTACTO = "https://github.com/MagliLuc/eventos"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/125.0.0.0 Safari/537.36 (+{CONTACTO}; agenda cultural gratuita)"
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "From": CONTACTO,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    return session


def fetch_soup(session: requests.Session, url: str,
               retries: int = 3) -> Optional[BeautifulSoup]:
    """GET con backoff exponencial. Devuelve None si la fuente no responde.

    Una fuente caida no debe romper la corrida: el pipeline conserva los
    eventos de las demas y el JSON publicado sigue siendo valido.
    """
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except Exception as exc:
            print(f"  [http] intento {attempt}/{retries} fallo en {url}: {exc}")
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
    return None


class Source:
    """Fuente de eventos. Las subclases implementan `fetch`.

    `fetch` recibe la ventana completa y se llama UNA vez por corrida: es
    responsabilidad de la fuente devolver todo lo que caiga dentro.
    """

    name: str = "generic"
    url: str = ""

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        raise NotImplementedError

    def safe_fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        try:
            events = self.fetch(session, window)
            print(f"  [{self.name}] {len(events)} eventos")
            return events
        except Exception as exc:  # una fuente rota no tumba la corrida
            print(f"  [{self.name}] ERROR: {type(exc).__name__}: {exc}")
            return []


# ---------------------------------------------------------------------------
# Extraccion generica
# ---------------------------------------------------------------------------
# Los sitios oficiales cambian su maquetado seguido. Por eso la estrategia
# principal es leer JSON-LD schema.org/Event, que WordPress y Drupal (el CMS
# de casi todas estas agendas) emiten en un <script type="application/ld+json">
# y que se rompe mucho menos que un selector CSS. El parseo por selectores
# queda como plan B y esta pensado para retocarse sin tocar el resto del
# pipeline: cada fuente declara sus selectores como atributos de clase.

import json as _json  # noqa: E402  (import local para no ensuciar la API)


def extract_jsonld_events(soup: BeautifulSoup) -> list[dict]:
    """Devuelve los nodos schema.org/Event embebidos en la pagina."""
    found: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(isinstance(t, str) and t.endswith("Event") for t in types):
                found.append(node)
            for key in ("@graph", "itemListElement", "item", "subEvent"):
                if key in node:
                    walk(node[key])

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            walk(_json.loads(raw))
        except _json.JSONDecodeError:
            continue
    return found


def text_of(node, selector: str) -> Optional[str]:
    """Texto del primer match del selector, o None."""
    if node is None:
        return None
    found = node.select_one(selector)
    return found.get_text(" ", strip=True) if found else None


def link_of(node, selector: str, base_url: str = "") -> Optional[str]:
    from urllib.parse import urljoin

    if node is None:
        return None
    found = node.select_one(selector)
    if not found or not found.get("href"):
        return None
    return urljoin(base_url, found["href"])
