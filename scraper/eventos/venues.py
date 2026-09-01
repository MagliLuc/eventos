"""Catalogo de sedes culturales de CABA con coordenadas.

Geocodificar cuesta $0 porque las sedes se repiten: el catalogo local
resuelve el 95% de los casos sin salir a la red. Para una sede nueva se
consulta Nominatim (OpenStreetMap), que es gratuito y no pide tarjeta ni
API key; se respeta su politica de uso (1 request/segundo y User-Agent
identificable) y el resultado se cachea en disco para no repetir la
consulta manana.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import NamedTuple, Optional

from .models import PARTIDOS_POR_ZONA, Venue, slugify

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "eventos-caba-bot/1.0 (https://github.com/MagliLuc/eventos)"
CACHE_PATH = Path(__file__).resolve().parent.parent / "geocache.json"

class Sede(NamedTuple):
    """Una sede del catalogo.

    Campos con nombre y no una tupla suelta a proposito: al sumar `zone` la
    tupla pasaba de 5 a 6 posiciones y habia que reeditar las 18 entradas
    contando comas, que es la forma tipica de meter un dato en el campo
    equivocado sin que nada falle. Con `zone` al final y con default, las
    entradas de CABA no cambian.
    """

    address: str
    neighborhood: str
    commune: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    zone: str = "CABA"


# Sedes conocidas, por id canonico.
#
# Las coordenadas pueden ir en None: `is_locatable` se conforma con la
# direccion, y una sede sin coordenadas se publica igual (no aparece en el
# mapa, nada mas). Es preferible eso a inventar un par de numeros: una
# coordenada equivocada manda a alguien al lugar equivocado, que es peor que
# no mostrarla. Lo mismo vale para la direccion: no se escribe de memoria,
# sale del HTML que sirvio el propio sitio.
KNOWN_VENUES: dict[str, Sede] = {
    "usina-del-arte": Sede("Caffarena 1", "La Boca", 4, -34.6390, -58.3576),
    "palacio-libertad": Sede("Sarmiento 151", "San Nicolás", 1, -34.6031, -58.3696),
    "centro-cultural-recoleta": Sede("Junín 1930", "Recoleta", 2, -34.5830, -58.3937),
    "casa-nacional-bicentenario": Sede("Riobamba 985", "Balvanera", 3, -34.5959, -58.3945),
    "museo-nacional-bellas-artes": Sede("Av. del Libertador 1473", "Recoleta", 2, -34.5838, -58.3919),
    "museo-del-cabildo": Sede("Bolívar 65", "Monserrat", 1, -34.6086, -58.3730),
    "museo-roca": Sede("Vicente López 2220", "Recoleta", 2, -34.5905, -58.3906),
    "teatro-colon": Sede("Libertad 621", "San Nicolás", 1, -34.6010, -58.3833),
    "planetario-galileo-galilei": Sede("Av. Sarmiento y Belisario Roldán", "Palermo", 14, -34.5697, -58.4118),
    "plaza-seeber": Sede("Av. Casares y Av. Sarmiento", "Palermo", 14, -34.5776, -58.4108),
    "feria-de-mataderos": Sede("Av. de los Corrales y Lisandro de la Torre", "Mataderos", 9, -34.6580, -58.5030),
    "teatro-san-martin": Sede("Av. Corrientes 1530", "San Nicolás", 1, -34.6041, -58.3894),
    "centro-cultural-25-de-mayo": Sede("Av. Triunvirato 4444", "Villa Urquiza", 12, -34.5722, -58.4863),
    "usina-cultural-sur": Sede("Av. Caseros 2739", "Parque Patricios", 4, -34.6367, -58.3979),
    "museo-sivori": Sede("Av. Infanta Isabel 555", "Palermo", 14, -34.5731, -58.4200),
    "parque-centenario": Sede("Av. Díaz Vélez y L. Marechal", "Caballito", 6, -34.6062, -58.4358),

    # Estas dos faltaban y costaban caro: sin entrada acá, `build_venue`
    # devolvía una sede sin dirección ni barrio, `is_locatable` la rechazaba, y
    # el pipeline tiraba los 40 eventos del Museo Moderno enteros. Las
    # direcciones salen del HTML que los propios sitios sirvieron y que quedó
    # guardado en scraper/diagnostico/, no de memoria.
    "museo-de-arte-moderno": Sede("Av. San Juan 350", "San Telmo", 1, None, None),
    "fundacion-proa": Sede("Av. Pedro de Mendoza 1929", "La Boca", 4, None, None),

    # Sedes del Conurbano: se agregan cuando la prospeccion apruebe la fuente
    # y su propio HTML de la direccion. Escribirlas ahora de memoria seria
    # justo lo que este archivo dice que no se hace.
}

# Alias frecuentes -> id canonico. Las agendas escriben la misma sede de
# muchas formas ("CCK", "Palacio Libertad", "ex CCK").
ALIASES: dict[str, str] = {
    "cck": "palacio-libertad",
    "centro-cultural-kirchner": "palacio-libertad",
    "ex-cck": "palacio-libertad",
    # El sitio se nombra a sí mismo de las dos formas: "Museo Moderno" en el
    # <title> de cada ficha y el nombre largo en el pie.
    "museo-moderno": "museo-de-arte-moderno",
    "museo-de-arte-moderno-de-buenos-aires": "museo-de-arte-moderno",
    "mamba": "museo-de-arte-moderno",
    "proa": "fundacion-proa",
    "usina": "usina-del-arte",
    "ccr": "centro-cultural-recoleta",
    "recoleta": "centro-cultural-recoleta",
    "cnb": "casa-nacional-bicentenario",
    "bellas-artes": "museo-nacional-bellas-artes",
    "mnba": "museo-nacional-bellas-artes",
    "cabildo": "museo-del-cabildo",
    "colon": "teatro-colon",
    "planetario": "planetario-galileo-galilei",
    "mataderos": "feria-de-mataderos",
}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# Partido normalizado -> zona, armado una sola vez desde PARTIDOS_POR_ZONA.
_ZONA_POR_PARTIDO: dict[str, str] = {
    slugify(partido): zona
    for zona, partidos in PARTIDOS_POR_ZONA.items()
    for partido in partidos
}


def zona_de_partido(nombre: Optional[str]) -> str:
    """Zona del AMBA a la que pertenece un partido. CABA si no es ninguno.

    Recibe un partido **declarado** (el campo `venue` de la fuente en
    `sources.json`), no prosa. Es a proposito: buscar nombres de partido
    dentro de una direccion se equivoca sola, y en nuestros propios datos ya
    hay con que -- "Vicente López 2220" es la direccion del Museo Roca, en
    Recoleta, y da lo mismo escrito que el partido de Vicente Lopez.
    """
    if not nombre:
        return "CABA"
    return _ZONA_POR_PARTIDO.get(slugify(nombre), "CABA")


def canonical_id(raw_name: str) -> str:
    """Normaliza el nombre de sede a un id canonico, resolviendo alias."""
    slug = slugify(raw_name)
    if slug in ALIASES:
        return ALIASES[slug]
    for known in KNOWN_VENUES:
        # "Palacio Libertad · Auditorio Nacional" -> "palacio-libertad"
        if slug.startswith(known):
            return known
    for alias, target in ALIASES.items():
        if slug.startswith(alias + "-") or slug == alias:
            return target
    return slug


def contexto_geografico(zona: str = "CABA", localidad: Optional[str] = None) -> str:
    """Cola de la consulta a Nominatim: donde buscar la direccion.

    Sin esto la busqueda decia siempre "Ciudad Autonoma de Buenos Aires", asi
    que una direccion del Conurbano caia en la calle homonima de Capital --
    "Av. Mitre 500" existe en media docena de partidos. Una coordenada
    equivocada es peor que ninguna: manda a alguien al lugar equivocado.
    """
    if zona == "CABA":
        return "Ciudad Autónoma de Buenos Aires, Argentina"
    partes = [p for p in (localidad, "Provincia de Buenos Aires", "Argentina") if p]
    return ", ".join(partes)


def geocode(query: str, session=None, zona: str = "CABA",
            localidad: Optional[str] = None) -> Optional[tuple[float, float]]:
    """Consulta Nominatim con cache en disco. Devuelve None si no resuelve."""
    contexto = contexto_geografico(zona, localidad)
    cache = _load_cache()
    # La clave incluye el contexto: la misma calle en dos partidos son dos
    # coordenadas distintas, y compartir entrada devolveria la de la otra.
    clave = query if zona == "CABA" and not localidad else f"{query} | {contexto}"
    if clave in cache:
        hit = cache[clave]
        return (hit["lat"], hit["lon"]) if hit else None

    if session is None:  # pragma: no cover - requiere red
        import requests

        session = requests.Session()

    try:  # pragma: no cover - requiere red
        time.sleep(1.1)  # politica de uso de Nominatim: max 1 req/s
        response = session.get(
            NOMINATIM_URL,
            params={"q": f"{query}, {contexto}", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json()
    except Exception as exc:
        print(f"  [geocode] fallo para '{query}': {exc}")
        return None

    if not results:
        cache[clave] = None
        _save_cache(cache)
        return None

    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    cache[clave] = {"lat": lat, "lon": lon}
    _save_cache(cache)
    return lat, lon


def build_venue(raw_name: str, raw_address: Optional[str] = None,
                geocode_unknown: bool = False,
                zone: Optional[str] = None,
                locality: Optional[str] = None) -> Venue:
    """Construye una Venue completando datos desde el catalogo local.

    `zone` y `locality` los pasa la fuente cuando la sede esta fuera de CABA;
    el catalogo local manda por sobre los dos cuando conoce la sede.
    """
    vid = canonical_id(raw_name)
    if vid in KNOWN_VENUES:
        sede = KNOWN_VENUES[vid]
        return Venue(
            id=vid,
            name=raw_name.strip(),
            address=raw_address or sede.address,
            neighborhood=sede.neighborhood,
            commune=sede.commune,
            lat=sede.lat,
            lon=sede.lon,
            zone=sede.zone,
        )

    zona = zone or zona_de_partido(locality)
    venue = Venue(
        id=vid,
        name=raw_name.strip(),
        address=raw_address,
        # Fuera de CABA la localidad hace de "barrio": es el nivel fino que
        # el filtro necesita, y sin el la sede tampoco es `is_locatable`.
        neighborhood=locality if zona != "CABA" else None,
        zone=zona,
    )
    if geocode_unknown:
        coords = geocode(raw_address or raw_name, zona=zona, localidad=locality)
        if coords:
            venue.lat, venue.lon = coords
    return venue
