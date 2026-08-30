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
from typing import Optional

from .models import Venue, slugify

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "eventos-caba-bot/1.0 (https://github.com/MagliLuc/eventos)"
CACHE_PATH = Path(__file__).resolve().parent.parent / "geocache.json"

# Sedes conocidas. name -> (address, neighborhood, commune, lat, lon)
KNOWN_VENUES: dict[str, tuple[str, str, int, float, float]] = {
    "usina-del-arte": ("Caffarena 1", "La Boca", 4, -34.6390, -58.3576),
    "palacio-libertad": ("Sarmiento 151", "San Nicolás", 1, -34.6031, -58.3696),
    "centro-cultural-recoleta": ("Junín 1930", "Recoleta", 2, -34.5830, -58.3937),
    "casa-nacional-bicentenario": ("Riobamba 985", "Balvanera", 3, -34.5959, -58.3945),
    "museo-nacional-bellas-artes": ("Av. del Libertador 1473", "Recoleta", 2, -34.5838, -58.3919),
    "museo-del-cabildo": ("Bolívar 65", "Monserrat", 1, -34.6086, -58.3730),
    "museo-roca": ("Vicente López 2220", "Recoleta", 2, -34.5905, -58.3906),
    "teatro-colon": ("Libertad 621", "San Nicolás", 1, -34.6010, -58.3833),
    "planetario-galileo-galilei": ("Av. Sarmiento y Belisario Roldán", "Palermo", 14, -34.5697, -58.4118),
    "plaza-seeber": ("Av. Casares y Av. Sarmiento", "Palermo", 14, -34.5776, -58.4108),
    "feria-de-mataderos": ("Av. de los Corrales y Lisandro de la Torre", "Mataderos", 9, -34.6580, -58.5030),
    "teatro-san-martin": ("Av. Corrientes 1530", "San Nicolás", 1, -34.6041, -58.3894),
    "centro-cultural-25-de-mayo": ("Av. Triunvirato 4444", "Villa Urquiza", 12, -34.5722, -58.4863),
    "usina-cultural-sur": ("Av. Caseros 2739", "Parque Patricios", 4, -34.6367, -58.3979),
    "museo-sivori": ("Av. Infanta Isabel 555", "Palermo", 14, -34.5731, -58.4200),
    "parque-centenario": ("Av. Díaz Vélez y L. Marechal", "Caballito", 6, -34.6062, -58.4358),
}

# Alias frecuentes -> id canonico. Las agendas escriben la misma sede de
# muchas formas ("CCK", "Palacio Libertad", "ex CCK").
ALIASES: dict[str, str] = {
    "cck": "palacio-libertad",
    "centro-cultural-kirchner": "palacio-libertad",
    "ex-cck": "palacio-libertad",
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


def geocode(query: str, session=None) -> Optional[tuple[float, float]]:
    """Consulta Nominatim con cache en disco. Devuelve None si no resuelve."""
    cache = _load_cache()
    if query in cache:
        hit = cache[query]
        return (hit["lat"], hit["lon"]) if hit else None

    if session is None:  # pragma: no cover - requiere red
        import requests

        session = requests.Session()

    try:  # pragma: no cover - requiere red
        time.sleep(1.1)  # politica de uso de Nominatim: max 1 req/s
        response = session.get(
            NOMINATIM_URL,
            params={"q": f"{query}, Ciudad Autónoma de Buenos Aires, Argentina",
                    "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json()
    except Exception as exc:
        print(f"  [geocode] fallo para '{query}': {exc}")
        return None

    if not results:
        cache[query] = None
        _save_cache(cache)
        return None

    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    cache[query] = {"lat": lat, "lon": lon}
    _save_cache(cache)
    return lat, lon


def build_venue(raw_name: str, raw_address: Optional[str] = None,
                geocode_unknown: bool = False) -> Venue:
    """Construye una Venue completando datos desde el catalogo local."""
    vid = canonical_id(raw_name)
    if vid in KNOWN_VENUES:
        address, neighborhood, commune, lat, lon = KNOWN_VENUES[vid]
        return Venue(
            id=vid,
            name=raw_name.strip(),
            address=raw_address or address,
            neighborhood=neighborhood,
            commune=commune,
            lat=lat,
            lon=lon,
        )

    venue = Venue(id=vid, name=raw_name.strip(), address=raw_address)
    if geocode_unknown:
        coords = geocode(raw_address or raw_name)
        if coords:
            venue.lat, venue.lon = coords
    return venue
