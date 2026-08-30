"""BA Data: portal oficial de datos abiertos del GCBA, sobre CKAN.

Es la fuente mas solida del proyecto y la unica con compromiso institucional
de actualizacion. La API de CKAN es publica: no pide API key, ni registro, ni
tarjeta. Se consulta el datastore del recurso y se mapean las columnas.

Los nombres de columna de estos datasets cambian entre publicaciones
(`titulo` / `nombre` / `evento`...), asi que en vez de hardcodear uno se
prueban varios alias por campo y se sigue de largo si ninguno esta.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any, Optional

import requests

from datetime import timedelta

from ..models import DateWindow, Event, now_ba_iso, today_ba
from ..normalize import clean_text, detect_access_mode, detect_category, is_free, parse_times
from ..venues import build_venue
from .base import Source

CKAN_BASE = "https://data.buenosaires.gob.ar/api/3/action"

# El diagnostico de columnas del 2026-08-30 mostro que casi todo lo que
# parecia una agenda en este portal es en realidad archivo o estadistica:
#
#   eventos-direccion-general-musica -> ultima fecha 2017-01-07
#   teatro-colon-visitas-guiadas     -> columnas PERIODO/VISITAS: conteos de
#                                       asistentes desde 2016, no eventos
#   ba-diversa                       -> asistentes_cantidad, desde 2015
#   bafici                           -> id_filmcolor: tabla de codigos
#
# BA Data es un portal de transparencia, no un feed de agenda. Quedan solo
# los dos ids que todavia podrian traer programacion vigente; el resto se
# saca para no descargar 9.500 filas historicas en cada corrida.
DATASETS = (
    "actividades-culturales",
    "teatro-colon-programacion-actual",
)

# Antiguedad a partir de la cual se considera que un dataset es archivo.
ANIOS_PARA_ARCHIVO = 2

# Terminos de busqueda para el fallback.
BUSQUEDAS = ("agenda cultural", "actividades culturales", "eventos culturales")

# Alias de columnas: el primero que aparezca con valor gana.
ALIAS = {
    "title": ("titulo", "nombre", "evento", "actividad", "title", "name"),
    "description": ("descripcion", "detalle", "resumen", "bajada", "description"),
    "date": ("fecha", "fecha_inicio", "fecha_desde", "start_date", "dia"),
    "time": ("hora", "horario", "hora_inicio", "start_time"),
    "venue": ("sede", "lugar", "espacio", "establecimiento", "venue", "nombre_sede"),
    "address": ("direccion", "domicilio", "calle", "address"),
    "neighborhood": ("barrio", "neighborhood"),
    "category": ("categoria", "disciplina", "tipo", "rubro", "category"),
    "price": ("precio", "costo", "arancel", "valor", "entrada"),
    "url": ("url", "link", "enlace", "web"),
    "lat": ("lat", "latitud", "latitude", "y"),
    "lon": ("lon", "long", "longitud", "longitude", "x"),
}


def _pick(row: dict, field: str) -> Optional[Any]:
    for alias in ALIAS[field]:
        for key, value in row.items():
            if key.strip().lower() == alias and value not in (None, "", "-"):
                return value
    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _as_iso_date(value: Any) -> Optional[str]:
    """Acepta 2026-08-30, 2026-08-30T20:00, 30/08/2026 y 30-08-2026."""
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    for sep in ("/", "-"):
        parts = text[:10].split(sep)
        if len(parts) == 3 and len(parts[0]) <= 2:
            day, month, year = parts
            if len(year) == 4:
                return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


class BaDataSource(Source):
    name = "BA Data (datos abiertos GCBA)"
    url = CKAN_BASE

    def fetch(self, session: requests.Session, window: DateWindow) -> list[Event]:
        # Se acumulan TODOS los datasets, no se corta en el primero que sirva:
        # cada uno trae actividades distintas (el Colon no se solapa con la
        # Direccion General de Musica). El dedupe del pipeline se ocupa si
        # alguna se repite.
        eventos: list[Event] = []
        for dataset in DATASETS:
            eventos.extend(self._del_dataset(session, dataset, window))

        # Solo si los ids conocidos no dieron nada se sale a buscar mas.
        if not eventos:
            for dataset in self._candidatos(session):
                if dataset not in DATASETS:
                    eventos.extend(self._del_dataset(session, dataset, window))

        if not eventos:
            self._diagnostico(session)
        return eventos

    def _del_dataset(self, session: requests.Session, dataset: str,
                     window: DateWindow) -> list[Event]:
        rows = self._rows(session, dataset)
        if not rows:
            return []
        eventos = [e for row in rows if (e := self._to_event(row, window))]
        print(f"  [{self.name}] '{dataset}': {len(rows)} filas "
              f"-> {len(eventos)} en ventana")

        # Bajar miles de filas y publicar cero es sospechoso: casi siempre
        # significa que no se encontro la columna de fecha, no que el dataset
        # sea historico. Se loguean las columnas reales y como quedo el
        # parseo de la primera fila, que es lo unico que distingue un caso
        # del otro sin tener acceso al portal.
        if rows and not eventos:
            muestra = rows[0]
            fecha_cruda = _pick(muestra, "date")
            print(f"  [{self.name}] '{dataset}' columnas: {list(muestra)[:14]}")
            print(f"  [{self.name}] '{dataset}' fecha detectada: "
                  f"{fecha_cruda!r} -> {_as_iso_date(fecha_cruda)!r} | "
                  f"titulo: {_pick(muestra, 'title')!r}")

            # La fecha mas nueva del dataset distingue "no encontre la
            # columna" de "esto es un archivo historico".
            fechas = [f for row in rows if (f := _as_iso_date(_pick(row, "date")))]
            if fechas:
                mas_nueva = max(fechas)
                corte = (today_ba() - timedelta(days=365 * ANIOS_PARA_ARCHIVO))
                aviso = " -> ARCHIVO, no sirve como agenda" if mas_nueva < corte.isoformat() else ""
                print(f"  [{self.name}] '{dataset}' fecha más nueva: "
                      f"{mas_nueva}{aviso}")
            else:
                print(f"  [{self.name}] '{dataset}' ninguna fila tiene fecha "
                      f"parseable -> falta un alias de columna")
        return eventos

    def _get(self, session: requests.Session, path: str, params: dict,
             intentos: int = 3) -> Optional[dict]:
        """GET con reintento ante 5xx.

        El portal contesta 502 de forma intermitente: en la corrida del
        2026-08-30 la misma URL dio 502 y, segundos despues, 200. Un 5xx es
        transitorio y merece reintento; un 404 no, y corta enseguida.
        """
        espera = 2.0
        for intento in range(1, intentos + 1):
            try:
                r = session.get(f"{CKAN_BASE}/{path}", params=params, timeout=30)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code} del portal")
                r.raise_for_status()
                return r.json()
            except requests.HTTPError as exc:
                if "404" in str(exc):
                    return None          # el dataset no existe: no insistir
                if intento < intentos:
                    time.sleep(espera)
                    espera *= 2
                    continue
                print(f"  [{self.name}] {path} agotó reintentos: {exc}")
            except Exception as exc:
                print(f"  [{self.name}] {path} falló: {exc}")
                return None
        return None

    def _candidatos(self, session: requests.Session) -> list[str]:
        """Ids fijos primero; si fallan, los que descubra la busqueda."""
        encontrados: list[str] = list(DATASETS)
        for termino in BUSQUEDAS:
            data = self._get(session, "package_search", {"q": termino, "rows": 8})
            for paquete in (data or {}).get("result", {}).get("results", []):
                nombre = paquete.get("name")
                if nombre and nombre not in encontrados:
                    encontrados.append(nombre)
                    print(f"  [{self.name}] descubierto por búsqueda: {nombre}")
        return encontrados

    def _diagnostico(self, session: requests.Session) -> None:
        """Lista los datasets del portal que suenan a agenda.

        Si ningun candidato sirvio, el log de la proxima corrida deja los ids
        reales anotados y no hay que salir a buscarlos a mano.
        """
        data = self._get(session, "package_list", {})
        nombres = (data or {}).get("result") or []
        if not nombres:
            return
        claves = ("agenda", "cultur", "evento", "actividad", "museo", "teatro")
        pistas = [n for n in nombres if any(k in n.lower() for k in claves)]
        print(f"  [{self.name}] el portal tiene {len(nombres)} datasets; "
              f"candidatos por nombre: {pistas[:25] or 'ninguno'}")

    def _rows(self, session: requests.Session, dataset: str) -> list[dict]:
        """Resuelve el dataset -> recurso con datastore -> filas."""
        data = self._get(session, "package_show", {"id": dataset})
        if not data:
            return []
        resources = data.get("result", {}).get("resources", [])

        # Camino 1: el datastore, que se consulta por API.
        for resource in resources:
            if not resource.get("datastore_active"):
                continue
            filas = self._get(
                session, "datastore_search",
                {"resource_id": resource["id"], "limit": 1000},
            )
            registros = (filas or {}).get("result", {}).get("records")
            if registros:
                return registros

        # Camino 2: bajar el CSV.
        # La mayoria de los datasets de BA Data publican archivos para
        # descarga y NO estan cargados al datastore, asi que quedarse solo
        # con el camino 1 los descarta a todos en silencio.
        for resource in resources:
            if (resource.get("format") or "").upper() not in ("CSV", "XLSX"):
                continue
            url = resource.get("url")
            if not url or not url.lower().endswith(".csv"):
                continue
            registros = self._csv(session, url)
            if registros:
                print(f"  [{self.name}] '{dataset}': CSV con {len(registros)} filas")
                return registros

        formatos = sorted({(r.get("format") or "?") for r in resources})
        print(f"  [{self.name}] '{dataset}': sin datos utilizables "
              f"(recursos: {formatos or 'ninguno'})")
        return []

    def _csv(self, session: requests.Session, url: str) -> list[dict]:
        """Descarga y parsea un CSV. Sin dependencias: csv es de la stdlib."""
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
        except Exception as exc:
            print(f"  [{self.name}] CSV {url[:60]}: {exc}")
            return []

        # Los CSV del GCBA vienen en UTF-8, a veces con BOM y a veces con ';'.
        texto = r.content.decode("utf-8-sig", errors="replace")
        muestra = texto[:4096]
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        try:
            return list(csv.DictReader(io.StringIO(texto), delimiter=delimitador))
        except csv.Error as exc:
            print(f"  [{self.name}] CSV ilegible: {exc}")
            return []

    def _to_event(self, row: dict, window: DateWindow) -> Optional[Event]:
        title = clean_text(_pick(row, "title"), 160)
        iso_date = _as_iso_date(_pick(row, "date"))
        if not title or not window.contains(iso_date):
            return None

        price = _pick(row, "price")
        description = clean_text(_pick(row, "description"))
        if not is_free(title, description, str(price or "")):
            return None

        start_time, end_time = parse_times(str(_pick(row, "time") or ""))
        venue = build_venue(
            str(_pick(row, "venue") or "Ciudad de Buenos Aires"),
            clean_text(_pick(row, "address"), 120),
        )
        if not venue.neighborhood:
            venue.neighborhood = clean_text(_pick(row, "neighborhood"), 60)
        if venue.lat is None:
            venue.lat = _as_float(_pick(row, "lat"))
            venue.lon = _as_float(_pick(row, "lon"))

        return Event(
            title=title,
            description=description,
            category=detect_category(title, description, str(_pick(row, "category") or "")),
            access_mode=detect_access_mode(title, description, str(price or "")),
            date=iso_date,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            source_name="BA Data",
            source_url=str(_pick(row, "url") or "https://data.buenosaires.gob.ar/"),
            updated_at=now_ba_iso(),
        )
