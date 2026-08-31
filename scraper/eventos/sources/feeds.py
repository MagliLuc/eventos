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
from urllib.parse import urljoin, urlparse

import requests

from ..fechas import extraer_fechas
from ..models import DateWindow, Event, now_ba_iso
from ..normalize import (
    clean_text,
    detect_access_mode,
    detect_category,
    is_explicitly_free,
    is_free,
    parse_times,
)
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


PALABRAS_EVENTO = ("evento", "agenda", "actividad", "cartelera", "espectaculo",
                   "muestra", "exposicion", "programacion", "funcion", "obra")

RUTAS_SITEMAP = ("/sitemap.xml", "/sitemap_index.xml")
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")


def urls_de_sitemap(session, base: str, filtro: str = "",
                    tope: int = 40) -> list[str]:
    """URLs de ficha sacadas del sitemap, siguiendo los índices.

    Hace falta porque varios listados se arman por JavaScript y no dejan un
    solo enlace que leer, pero el sitemap sí lista cada actividad. Y hay que
    seguir los índices: `sitemap.xml` suele ser sólo un índice que apunta a
    `production-sitemap.xml` o similar, que es donde están los eventos de
    verdad. Sin esto se leían los índices como si fueran fichas.
    """
    for ruta in RUTAS_SITEMAP:
        try:
            r = session.get(urljoin(base, ruta), timeout=25)
            if r.status_code != 200:
                continue
        except Exception:
            continue

        urls = LOC_RE.findall(r.text)
        if "<sitemapindex" in r.text:
            # Es un índice: bajar a los sub-sitemaps que suenen a evento.
            hojas = [u for u in urls
                     if any(p in u.lower() for p in PALABRAS_EVENTO)] or urls[:3]
            urls = []
            for hoja in hojas[:3]:
                try:
                    rh = session.get(hoja, timeout=25)
                    if rh.status_code == 200:
                        urls.extend(LOC_RE.findall(rh.text))
                except Exception:
                    continue

        # Un sub-sitemap no vuelve a filtrarse por palabra: ya lo dijo su
        # nombre, y adentro las URLs pueden no repetirla.
        candidatas = [u for u in urls if not u.endswith(".xml")]
        if filtro:
            candidatas = [u for u in candidatas if filtro in u.lower()]
        elif "<sitemapindex" not in r.text:
            candidatas = [u for u in candidatas
                          if any(p in u.lower() for p in PALABRAS_EVENTO)]
        if candidatas:
            return candidatas[:tope]
    return []


class LectorDeFichas(Source):
    """Entra a la ficha de cada actividad y saca el evento de ahí.

    Es la respuesta a los dos problemas que más fuentes nos costaron:

      * un ítem de RSS es un *artículo*, no un evento: no trae fecha de evento
        ni sede;
      * varios listados dan 200 sin marcado porque se arman por JavaScript,
        pero la ficha de cada actividad sí emite schema.org/Event, que el CMS
        genera solo.

    En los dos casos la salida es la misma: juntar URLs de ficha (de un feed o
    de los enlaces del listado) y leer cada una. Primero JSON-LD; si no hay, la
    prosa, exigiendo que la fecha esté escrita y que diga que es gratis. Sin
    eso, se descarta: preferimos publicar menos y correcto antes que fabricar
    fechas, que es exactamente el bug que ya tuvimos una vez.
    """

    default_venue: str = ""
    max_items: int = 15

    def _leer_fichas(self, session, enlaces: list[str], window: DateWindow,
                     titulos: dict[str, str] | None = None,
                     contexto: dict[str, str] | None = None) -> list[Event]:
        titulos, contexto = titulos or {}, contexto or {}
        eventos: list[Event] = []
        sin_marcado = sin_fecha = sin_precio = 0

        for enlace in enlaces[: self.max_items]:
            sopa = fetch_soup(session, enlace, retries=1)
            if sopa is None:
                continue

            nodos = extract_jsonld_events(sopa)
            if nodos:
                for nodo in nodos:
                    evento = self._de_jsonld(nodo, window, enlace)
                    if evento:
                        eventos.append(evento)
                continue

            sin_marcado += 1
            desde_texto, motivo = self._de_texto(
                sopa, {"title": titulos.get(enlace)}, window, enlace,
                contexto.get(enlace, ""))
            eventos.extend(desde_texto)
            sin_fecha += motivo == "fecha"
            sin_precio += motivo == "precio"

        if sin_marcado:
            print(f"  [{self.name}] {sin_marcado} fichas sin schema.org/Event "
                  f"(leidas como texto: {sin_fecha} sin fecha escrita, "
                  f"{sin_precio} sin decir que sean gratis)")
        return eventos

    # -- Plan B: la ficha en prosa ----------------------------------------
    def _de_texto(self, sopa, entrada: dict, window: DateWindow,
                  enlace: str, tarjeta: str = "") -> tuple[list[Event], str]:
        """Arma eventos leyendo la nota. Devuelve (eventos, motivo del cero).

        Se mira solo el titulo y la entradilla, no la nota entera: la fecha de
        la actividad esta arriba, y mas abajo aparecen fechas de otras cosas
        que meterian eventos que no son.

        `tarjeta` es el texto del listado que enlazaba a esta ficha. Va aparte
        porque muchas veces es donde esta la fecha ("Desde el jueves 20.08 |
        18 h") mientras la ficha solo describe la actividad.
        """
        titular = sopa.find("h1")
        titulo = clean_text(
            (titular.get_text(" ", strip=True) if titular else None)
            or entrada.get("title"), 160)
        if not titulo:
            return [], "titulo"

        cuerpo = sopa.find("article") or sopa.find("main") or sopa
        parrafos = [p.get_text(" ", strip=True) for p in cuerpo.find_all("p")[:6]]
        entradilla = " ".join(p for p in parrafos if p)[:900]
        clave = f"{titulo}. {entradilla}"

        if not is_explicitly_free(f"{clave} {tarjeta}"):
            return [], "precio"

        # La ficha manda; la tarjeta es el respaldo.
        fechas = extraer_fechas(clave, window) or extraer_fechas(tarjeta, window)
        if not fechas:
            return [], "fecha"

        inicio, fin = parse_times(clave)
        if not inicio:
            inicio, fin = parse_times(tarjeta)
        descripcion = clean_text(entradilla)
        return [
            Event(
                title=titulo,
                description=descripcion,
                category=detect_category(titulo, descripcion),
                access_mode=detect_access_mode(titulo, descripcion),
                date=fecha,
                start_time=inicio,
                end_time=fin,
                venue=build_venue(self.default_venue),
                source_name=self.name,
                source_url=enlace,
                updated_at=now_ba_iso(),
            )
            for fecha in fechas
        ], ""

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


class RssSource(LectorDeFichas):
    """Feed RSS/Atom: se usa solo para descubrir qué fichas leer."""

    def __init__(self, name: str, url: str, default_venue: str = "",
                 max_items: int = 15):
        self.name, self.url = name, url
        self.default_venue, self.max_items = default_venue, max_items

    def fetch(self, session, window: DateWindow) -> list[Event]:
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

        enlaces, titulos = [], {}
        for entrada in entradas:
            enlace = entrada.get("link")
            if enlace and enlace not in titulos:
                enlaces.append(enlace)
                titulos[enlace] = entrada.get("title") or ""
        return self._leer_fichas(session, enlaces, window, titulos)


class FichasSource(LectorDeFichas):
    """Listado HTML sin marcado, pero con fichas que sí lo tienen.

    El listado se usa solo como índice: se juntan los enlaces que parecen
    ficha de actividad y se lee cada uno. Es preferible a los selectores CSS
    porque no depende del maquetado del listado, que es lo que más cambia.
    """

    def __init__(self, name: str, url: str, default_venue: str = "",
                 max_items: int = 15, ruta_ficha: str = ""):
        self.name, self.url = name, url
        self.default_venue, self.max_items = default_venue, max_items
        # Opcional: fragmento que debe aparecer en la ruta de la ficha, para
        # cuando las palabras genéricas traen de más (p. ej. "/actividad/").
        self.ruta_ficha = ruta_ficha

    @property
    def base(self) -> str:
        partes = urlparse(self.url)
        return f"{partes.scheme}://{partes.netloc}"

    def fetch(self, session, window: DateWindow) -> list[Event]:
        contexto: dict[str, str] = {}
        enlaces: list[str] = []

        sopa = fetch_soup(session, self.url)
        if sopa is not None:
            enlaces, contexto = self._fichas(sopa)
            if enlaces:
                print(f"  [{self.name}] {len(enlaces)} fichas en el listado")

        if not enlaces:
            # Varios listados se arman por JavaScript y no dejan un enlace que
            # leer, pero su sitemap lista cada actividad igual.
            enlaces = urls_de_sitemap(session, self.base, self.ruta_ficha)
            if enlaces:
                print(f"  [{self.name}] {len(enlaces)} fichas por sitemap "
                      f"(el listado no expone enlaces)")

        if not enlaces:
            print(f"  [{self.name}] sin fichas ni por listado ni por sitemap")
            return []
        return self._leer_fichas(session, enlaces, window, contexto=contexto)

    def _fichas(self, sopa) -> tuple[list[str], dict[str, str]]:
        """Enlaces de ficha y el texto de la tarjeta que los contiene.

        La tarjeta importa: en varios listados la fecha está ahí y no en la
        ficha ("Desde el jueves 20.08 | 18 h"). Guardarla evita perder el
        evento cuando la ficha describe la actividad sin fecharla.
        """
        encontrados: list[str] = []
        contexto: dict[str, str] = {}
        for a in sopa.find_all("a", href=True):
            destino = urljoin(self.url, a["href"]).split("#")[0]
            if not destino.startswith(self.base):
                continue
            if destino.rstrip("/") == self.url.rstrip("/"):
                continue
            ruta = urlparse(destino).path.lower()
            if self.ruta_ficha:
                calza = self.ruta_ficha in ruta
            else:
                # Una ficha vive un nivel más adentro que el listado; el
                # segmento extra evita traerse el propio menú del sitio.
                calza = (any(p in ruta for p in PALABRAS_EVENTO)
                         and len(ruta.strip("/").split("/")) >= 2)
            if not calza or destino in contexto:
                continue
            encontrados.append(destino)
            contexto[destino] = _texto_de_la_tarjeta(a)
        return encontrados, contexto


def _texto_de_la_tarjeta(enlace) -> str:
    """Sube por el DOM hasta el primer ancestro con texto suficiente."""
    nodo = enlace
    for _ in range(5):
        nodo = nodo.parent
        if nodo is None:
            break
        texto = nodo.get_text(" ", strip=True)
        if len(texto) > 40:
            return texto[:400]
    return enlace.get_text(" ", strip=True)[:400]
