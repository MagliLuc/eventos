"""Contrato comun de las fuentes y helper HTTP con reintentos."""
from __future__ import annotations

import time
from typing import Optional

from bs4 import BeautifulSoup

from ..http import (  # re-exportados: el resto del scraper los importa de aca
    BROWSER_HEADERS,
    CONTACTO,
    USER_AGENT,
    PoliteSession,
    RobotsBloqueado,
    http_session,
)
from ..informe import InformeFuente
from ..models import DateWindow, Event

__all__ = [
    "InformeFuente",
    "BROWSER_HEADERS", "CONTACTO", "USER_AGENT", "PoliteSession",
    "RobotsBloqueado", "http_session", "fetch_soup", "Source",
    "extract_jsonld_events", "text_of", "link_of",
]


def fetch_soup(session, url: str, retries: int = 3,
               timeout: Optional[int] = None) -> Optional[BeautifulSoup]:
    """GET con backoff exponencial. Devuelve None si la fuente no responde.

    Una fuente caida no debe romper la corrida: el pipeline conserva los
    eventos de las demas y el JSON publicado sigue siendo valido.
    """
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except RobotsBloqueado as exc:
            # Reintentar no cambia nada y seria insistir donde nos dijeron que no.
            print(f"  [http] {exc}")
            return None
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

    # Id estable para la app. Se separa de `name` porque el nombre humano se
    # repite: la semilla curada publica eventos con source_name "Centro
    # Cultural Recoleta", igual que la fuente en vivo del mismo nombre. Sin un
    # id propio, el panel mostraria el estado del scraper sobre eventos que no
    # salieron de ahi.
    @property
    def id(self) -> str:
        from ..models import slugify
        return slugify(self.name)

    # Lo que la fuente quiere contar de la corrida: cuantas fichas leyo y por
    # que descarto las que descarto. Lo llena `_leer_fichas`; las fuentes que
    # no leen fichas lo dejan vacio y su estado sale solo de si trajo eventos.
    _ultimos_motivos: dict[str, int]
    _ultimas_fichas: int

    # Una fuente puede pedir un transporte propio: IPv4 forzado cuando el
    # dominio tiene AAAA sin ruta real (sintoma: ConnectTimeout) o un timeout
    # mas largo si el sitio es lento. Vacio = usa la sesion compartida.
    force_ipv4: bool = False
    timeout: Optional[int] = None

    def fetch(self, session, window: DateWindow) -> list[Event]:
        raise NotImplementedError

    def _session_propia(self, compartida):
        """Sesion dedicada solo si la fuente pide algo distinto."""
        if not (self.force_ipv4 or self.timeout):
            return compartida
        sesion = http_session(force_ipv4=self.force_ipv4,
                              timeout=self.timeout or 30)
        print(f"  [{self.name}] transporte propio: {sesion.transporte}"
              f"{', IPv4 forzado' if self.force_ipv4 else ''}"
              f", timeout {sesion.timeout}s")
        return sesion

    def safe_fetch(self, session, window: DateWindow) -> list[Event]:
        """Compatibilidad: solo los eventos. El informe queda en `ultimo_informe`."""
        events, _ = self.fetch_con_informe(session, window)
        return events

    def fetch_con_informe(self, session,
                          window: DateWindow) -> tuple[list[Event], InformeFuente]:
        """Corre la fuente y devuelve tambien como le fue.

        El informe sale de aca y no del pipeline porque este es el unico lugar
        que ve la excepcion: antes se imprimia y se perdia, y entonces "0
        eventos" en el log podia ser tanto un sitio caido como una agenda sin
        nada gratis. Son cosas distintas y ahora se distinguen.
        """
        self._ultimos_motivos = {}
        self._ultimas_fichas = 0
        informe = InformeFuente(id=self.id, nombre=self.name, url=self.url or None)
        try:
            events = self.fetch(self._session_propia(session), window)
        except Exception as exc:  # una fuente rota no tumba la corrida
            print(f"  [{self.name}] ERROR: {type(exc).__name__}: {exc}")
            informe.error = f"{type(exc).__name__}: {exc}"
            return [], informe

        informe.eventos = len(events)
        informe.motivos = dict(self._ultimos_motivos)
        # Sin fichas contadas (ICS, Tribe, semilla), cada evento cuenta como
        # una lectura: si no, `estado` los tomaria por inalcanzables.
        informe.fichas = self._ultimas_fichas or len(events)
        print(f"  [{self.name}] {len(events)} eventos -> {informe.estado}")
        return events, informe


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
