"""Extractores genéricos, uno por mecanismo de publicación.

La idea es que agregar una fuente sea *configuración*, no código: cada clase
de acá sabe leer un formato, y `sources.json` dice qué sitio se lee con cuál.

Orden de preferencia, de más a menos confiable:

  1. ICS          — calendario estándar: fecha, hora y lugar ya normalizados.
  2. Tribe (WP)   — The Events Calendar, el plugin de eventos más usado en
                    WordPress. Expone /wp-json/tribe/events/v1/events con
                    start_date, venue y cost: es una API de eventos de verdad.
  3. JSON-LD      — schema.org/Event embebido en el HTML.
  4. WP posts     — /wp-json/wp/v2/posts. Da artículos, no eventos: sirve para
                    descubrir fichas que después se leen por JSON-LD.
  5. RSS/Atom     — igual que arriba, pero sin depender de WordPress.
  6. Selectores   — último recurso (ver html_source.py).

Todo con la stdlib: `csv`, `xml.etree` y `json`. Sin dependencias nuevas.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterable, Optional

import requests

from ..models import DateWindow, Event, now_ba_iso
from ..normalize import clean_text, detect_access_mode, detect_category, is_free, parse_times
from ..venues import build_venue
from .base import Source, extract_jsonld_events, fetch_soup


# ---------------------------------------------------------------------------
# iCalendar
# ---------------------------------------------------------------------------

def _unfold(texto: str) -> list[str]:
    """RFC 5545: una línea larga se parte y continúa con espacio o tab."""
    lineas: list[str] = []
    for cruda in texto.splitlines():
        if cruda[:1] in (" ", "\t") and lineas:
            lineas[-1] += cruda[1:]
        else:
            lineas.append(cruda)
    return lineas


def parse_ics(texto: str) -> list[dict]:
    """Devuelve los VEVENT como diccionarios de propiedad -> valor."""
    eventos: list[dict] = []
    actual: Optional[dict] = None
    for linea in _unfold(texto):
        if linea.startswith("BEGIN:VEVENT"):
            actual = {}
        elif linea.startswith("END:VEVENT"):
            if actual:
                eventos.append(actual)
            actual = None
        elif actual is not None and ":" in linea:
            clave, valor = linea.split(":", 1)
            # DTSTART;TZID=America/Argentina/Buenos_Aires -> DTSTART
            nombre = clave.split(";", 1)[0].upper()
            # Los \n y \, del formato vienen escapados.
            actual[nombre] = valor.replace("\\n", " ").replace("\\,", ",").strip()
    return eventos


def _ics_fecha_hora(valor: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """20260905T200000 / 20260905 / 2026-09-05T20:00:00Z -> (fecha, hora)."""
    if not valor:
        return None, None
    limpio = valor.replace("-", "").replace(":", "").rstrip("Z")
    if len(limpio) >= 8 and limpio[:8].isdigit():
        fecha = f"{limpio[:4]}-{limpio[4:6]}-{limpio[6:8]}"
        hora = None
        if len(limpio) >= 13 and limpio[8] == "T":
            hora = f"{limpio[9:11]}:{limpio[11:13]}"
        return fecha, hora
    return None, None


class IcsSource(Source):
    """Calendario iCalendar. Es el formato ideal: ya viene normalizado."""

    def __init__(self, name: str, url: str, default_venue: str = ""):
        self.name, self.url, self.default_venue = name, url, default_venue

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        try:
            r = session.get(self.url, timeout=45)
            r.raise_for_status()
        except Exception as exc:
            print(f"  [{self.name}] ICS no responde: {exc}")
            return []

        eventos = []
        for vevent in parse_ics(r.text):
            fecha, hora = _ics_fecha_hora(vevent.get("DTSTART"))
            titulo = clean_text(vevent.get("SUMMARY"), 160)
            if not titulo or not window.contains(fecha):
                continue
            descripcion = clean_text(vevent.get("DESCRIPTION"))
            if not is_free(titulo, descripcion):
                continue
            _, hora_fin = _ics_fecha_hora(vevent.get("DTEND"))
            eventos.append(Event(
                title=titulo,
                description=descripcion,
                category=detect_category(titulo, descripcion, vevent.get("CATEGORIES")),
                access_mode=detect_access_mode(titulo, descripcion),
                date=fecha,
                start_time=hora,
                end_time=hora_fin,
                venue=build_venue(vevent.get("LOCATION") or self.default_venue),
                source_name=self.name,
                source_url=vevent.get("URL") or self.url,
                updated_at=now_ba_iso(),
            ))
        return eventos


# ---------------------------------------------------------------------------
# WordPress · The Events Calendar
# ---------------------------------------------------------------------------

class TribeEventsSource(Source):
    """The Events Calendar (plugin de WordPress).

    Es el mejor caso posible después de ICS: devuelve JSON con `start_date`,
    `venue` desglosado y `cost`, así que el filtro de gratuidad sale del dato
    y no de adivinar sobre texto libre.
    """

    def __init__(self, name: str, url: str, default_venue: str = ""):
        self.name = name
        self.url = url.rstrip("/")
        self.default_venue = default_venue

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        params = {
            "start_date": window.start.isoformat(),
            "end_date": window.end.isoformat(),
            "per_page": 50,
        }
        try:
            r = session.get(self.url, params=params, timeout=45)
            r.raise_for_status()
            datos = r.json()
        except Exception as exc:
            print(f"  [{self.name}] Tribe no responde: {exc}")
            return []

        eventos = []
        for crudo in datos.get("events", []):
            titulo = clean_text(crudo.get("title"), 160)
            fecha = (crudo.get("start_date") or "")[:10]
            if not titulo or not window.contains(fecha):
                continue

            costo = str(crudo.get("cost") or "").strip()
            descripcion = clean_text(_sin_html(crudo.get("description")))
            # `cost` vacío en Tribe suele significar "sin precio cargado", no
            # necesariamente gratis: se confirma contra el texto.
            if costo and not re.fullmatch(r"0([.,]0+)?|gratis|free|libre", costo, re.I):
                continue
            if not is_free(titulo, descripcion, costo):
                continue

            sede = crudo.get("venue") or {}
            eventos.append(Event(
                title=titulo,
                description=descripcion,
                category=detect_category(titulo, descripcion,
                                         " ".join(c.get("name", "") for c in crudo.get("categories", []))),
                access_mode=detect_access_mode(titulo, descripcion, costo,
                                               str(crudo.get("website") or "")),
                date=fecha,
                start_time=(crudo.get("start_date") or "")[11:16] or None,
                end_time=(crudo.get("end_date") or "")[11:16] or None,
                venue=build_venue(sede.get("venue") or self.default_venue,
                                  sede.get("address")),
                reservation_url=crudo.get("website") or None,
                source_name=self.name,
                source_url=crudo.get("url") or self.url,
                image_url=(crudo.get("image") or {}).get("url") if isinstance(crudo.get("image"), dict) else None,
                updated_at=now_ba_iso(),
            ))
        return eventos


def _sin_html(texto: Optional[str]) -> Optional[str]:
    return re.sub(r"<[^>]+>", " ", texto) if texto else None


# ---------------------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------------------

def parse_feed(texto: str) -> list[dict]:
    """RSS 2.0 y Atom con la misma salida: title, link, summary, date."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entradas: list[dict] = []

    for item in raiz.iter():
        etiqueta = item.tag.split("}")[-1]
        if etiqueta not in ("item", "entry"):
            continue

        def texto_de(*nombres: str) -> Optional[str]:
            for nombre in nombres:
                hijo = item.find(nombre) if "}" not in nombre else item.find(nombre, ns)
                if hijo is None:
                    hijo = item.find(f"{{http://www.w3.org/2005/Atom}}{nombre}")
                if hijo is not None and (hijo.text or "").strip():
                    return hijo.text.strip()
            return None

        enlace = texto_de("link")
        if not enlace:  # Atom pone el link en un atributo
            nodo = item.find("{http://www.w3.org/2005/Atom}link")
            enlace = nodo.get("href") if nodo is not None else None

        entradas.append({
            "title": texto_de("title"),
            "link": enlace,
            "summary": texto_de("description", "summary", "content"),
            "date": texto_de("pubDate", "published", "updated"),
        })
    return entradas


class RssSource(Source):
    """Feed de un portal o blog.

    Ojo con la expectativa: un ítem de RSS es un *artículo*, no un evento. No
    trae fecha de evento ni sede. Por eso, en vez de inventar esos datos, se
    entra a cada ficha enlazada y se busca JSON-LD schema.org/Event ahí. Si la
    nota no marca eventos, la entrada se descarta: preferimos publicar menos y
    correcto antes que fabricar fechas.
    """

    def __init__(self, name: str, url: str, default_venue: str = "",
                 max_items: int = 15):
        self.name, self.url = name, url
        self.default_venue, self.max_items = default_venue, max_items

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        try:
            r = session.get(self.url, timeout=45)
            r.raise_for_status()
        except Exception as exc:
            print(f"  [{self.name}] feed no responde: {exc}")
            return []

        entradas = parse_feed(r.text)
        if not entradas:
            print(f"  [{self.name}] el feed no parsea como RSS/Atom")
            return []

        eventos: list[Event] = []
        sin_marcado = 0
        for entrada in entradas[: self.max_items]:
            enlace = entrada.get("link")
            if not enlace:
                continue
            sopa = fetch_soup(session, enlace, retries=1)
            if sopa is None:
                continue
            nodos = extract_jsonld_events(sopa)
            if not nodos:
                sin_marcado += 1
                continue
            for nodo in nodos:
                evento = self._de_jsonld(nodo, window, enlace)
                if evento:
                    eventos.append(evento)

        if sin_marcado:
            print(f"  [{self.name}] {sin_marcado} notas sin schema.org/Event")
        return eventos

    def _de_jsonld(self, nodo: dict, window: DateWindow,
                   origen: str) -> Optional[Event]:
        titulo = clean_text(nodo.get("name"), 160)
        inicio = nodo.get("startDate") or ""
        if not titulo or not window.contains(inicio):
            return None
        descripcion = clean_text(nodo.get("description"))
        if not is_free(titulo, descripcion):
            return None

        lugar = nodo.get("location") or {}
        if isinstance(lugar, list):
            lugar = lugar[0] if lugar else {}
        direccion = lugar.get("address")
        if isinstance(direccion, dict):
            direccion = direccion.get("streetAddress")

        return Event(
            title=titulo,
            description=descripcion,
            category=detect_category(titulo, descripcion),
            access_mode=detect_access_mode(titulo, descripcion),
            date=inicio[:10],
            start_time=inicio[11:16] or None,
            end_time=(nodo.get("endDate") or "")[11:16] or None,
            venue=build_venue(lugar.get("name") or self.default_venue, direccion),
            source_name=self.name,
            source_url=nodo.get("url") or origen,
            updated_at=now_ba_iso(),
        )
