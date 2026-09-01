"""Fuente HTML generica: JSON-LD primero, selectores CSS como respaldo."""
from __future__ import annotations

from typing import Optional

import requests

from ..models import DateWindow, Event, now_ba_iso
from ..normalize import (
    clean_text,
    detect_access_mode,
    detect_contribution,
    detect_category,
    is_free,
    parse_times,
)
from ..venues import build_venue
from .base import Source, extract_jsonld_events, fetch_soup, link_of, text_of


class HtmlAgendaSource(Source):
    """Base para agendas web.

    Las subclases solo declaran `name`, `url`, la sede por defecto y sus
    selectores CSS. Si el sitio cambia el maquetado, ajustar los selectores
    de la subclase alcanza: la logica de normalizacion no se toca.
    """

    default_venue: str = ""
    # Plan B por selectores CSS (usado solo si no hay JSON-LD utilizable).
    item_selector: str = "article"
    title_selector: str = "h2, h3"
    date_selector: str = "time, .fecha, .date"
    time_selector: str = ".hora, .time, time"
    venue_selector: str = ".sede, .lugar, .venue"
    summary_selector: str = "p"
    link_selector: str = "a"

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        soup = fetch_soup(session, self.url)
        if soup is None:
            return []

        events = [
            event
            for node in extract_jsonld_events(soup)
            if (event := self._from_jsonld(node, window))
        ]
        if events:
            return events

        print(f"  [{self.name}] sin JSON-LD utilizable, uso selectores CSS")
        self._sin_fecha = 0
        events = [
            event
            for node in soup.select(self.item_selector)
            if (event := self._from_html(node, window))
        ]
        if self._sin_fecha:
            # Sintoma tipico de selectores desactualizados: la pagina lista
            # cosas pero ninguna trae fecha legible.
            print(f"  [{self.name}] {self._sin_fecha} descartados sin fecha legible")
        return events

    # -- JSON-LD ----------------------------------------------------------
    def _from_jsonld(self, node: dict, window: DateWindow) -> Optional[Event]:
        title = clean_text(node.get("name"), 160)
        start = node.get("startDate") or ""
        if not title or not window.contains(start):
            return None

        description = clean_text(node.get("description"))
        price, offer_text = oferta_de(node)
        if tiene_precio(price):
            return None  # la app solo lista actividades gratuitas
        if not is_free(title, description, offer_text):
            return None

        location = node.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        venue_name = location.get("name") or self.default_venue
        address = location.get("address")
        if isinstance(address, dict):
            address = address.get("streetAddress")

        return Event(
            title=title,
            description=description,
            category=detect_category(title, description),
            access_mode=detect_access_mode(title, description, offer_text,
                                           str(offers.get("url", ""))),
            contribution=detect_contribution(title, description, offer_text, str(offers.get("url", ""))),
            date=start[:10],
            start_time=start[11:16] or None,
            end_time=None if self.ignorar_hora_fin
                     else ((node.get("endDate") or "")[11:16] or None),
            venue=build_venue(venue_name, address, locality=self.partido),
            reservation_url=offers.get("url") or None,
            source_name=self.name,
            source_url=node.get("url") or self.url,
            image_url=_first_image(node.get("image")),
            updated_at=now_ba_iso(),
        )

    # -- Selectores CSS ---------------------------------------------------
    def _from_html(self, node, window: DateWindow) -> Optional[Event]:
        title = clean_text(text_of(node, self.title_selector), 160)
        if not title:
            return None

        date_text = text_of(node, self.date_selector) or ""
        time_node = node.select_one(self.date_selector)
        iso_date = (time_node.get("datetime", "")[:10] if time_node else "")

        # Sin fecha legible se descarta. Antes se asumia la fecha pedida, y
        # como el pipeline llamaba a la fuente una vez por dia, un mismo
        # evento terminaba clonado con una fecha distinta por cada llamada.
        if not window.contains(iso_date):
            self._sin_fecha = getattr(self, "_sin_fecha", 0) + 1
            return None

        summary = clean_text(text_of(node, self.summary_selector))
        blob = " ".join(filter(None, [title, summary, date_text]))
        if not is_free(blob):
            return None

        start_time, end_time = parse_times(
            text_of(node, self.time_selector) or date_text
        )
        return Event(
            title=title,
            description=summary,
            category=detect_category(title, summary),
            access_mode=detect_access_mode(blob),
            contribution=detect_contribution(blob),
            date=iso_date,
            start_time=start_time,
            end_time=end_time,
            venue=build_venue(text_of(node, self.venue_selector) or self.default_venue,
                              locality=self.partido),
            source_name=self.name,
            source_url=link_of(node, self.link_selector, self.url) or self.url,
            updated_at=now_ba_iso(),
        )


def _first_image(image) -> Optional[str]:
    if isinstance(image, str):
        return image
    if isinstance(image, list) and image:
        return _first_image(image[0])
    if isinstance(image, dict):
        return image.get("url")
    return None
