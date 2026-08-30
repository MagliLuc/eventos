"""Modelo de datos compartido entre el scraper y la app Android.

El JSON que produce este paquete es el contrato con el cliente Kotlin
(`docs/events.json` -> `EventDto` -> `EventEntity`). Cualquier cambio aca
tiene que reflejarse en `docs/events.schema.json` y en las data classes de
Kotlin.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1

# El runner de GitHub Actions corre en UTC, pero "hoy" en esta app siempre
# significa hoy en Buenos Aires. Sin esto, una corrida nocturna publicaria
# la agenda del dia equivocado.
BUENOS_AIRES = ZoneInfo("America/Argentina/Buenos_Aires")


def today_ba() -> date:
    """Fecha actual en Buenos Aires, independiente del huso del runner."""
    return datetime.now(BUENOS_AIRES).date()


def now_ba_iso() -> str:
    return datetime.now(BUENOS_AIRES).isoformat(timespec="seconds")


@dataclass(frozen=True)
class DateWindow:
    """Rango de fechas que se quiere publicar, en hora de Buenos Aires.

    Las fuentes reciben la ventana entera y se descargan UNA sola vez. Antes
    se las llamaba una vez por dia, lo que multiplicaba los requests por la
    cantidad de dias y, cuando la pagina no traia fecha legible, clonaba el
    mismo evento con una fecha distinta por cada llamada.
    """

    start: date
    end: date

    @classmethod
    def upcoming(cls, days: int) -> "DateWindow":
        today = today_ba()
        return cls(start=today, end=today + timedelta(days=max(days - 1, 0)))

    def contains(self, value: Optional[str]) -> bool:
        """`value` es una fecha ISO (YYYY-MM-DD); un valor invalido no entra."""
        if not value:
            return False
        try:
            parsed = date.fromisoformat(value[:10])
        except ValueError:
            return False
        return self.start <= parsed <= self.end

    def __str__(self) -> str:
        return f"{self.start} a {self.end}"

CATEGORIES = (
    "MUSICA",
    "ARTES_VISUALES",
    "CINE",
    "TEATRO",
    "INFANTILES",
    "FERIAS",
    "OTROS",
)

ACCESS_MODES = ("INGRESO_LIBRE", "ORDEN_DE_LLEGADA", "RESERVA_PREVIA")


def slugify(text: str) -> str:
    """Slug ASCII estable, usado para construir ids reproducibles."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    return ascii_text.strip("-")


@dataclass
class Venue:
    id: str
    name: str
    address: Optional[str] = None
    neighborhood: Optional[str] = None
    commune: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    @property
    def is_locatable(self) -> bool:
        """Si no se puede ubicar, el evento no sirve para esta app.

        Las agendas publican paginas indice ("Que hacer esta semana") con
        marcado schema.org/Event pero sin `location`. Al caer en la sede por
        defecto de la fuente quedan sin direccion, sin barrio y sin
        coordenadas: no se pueden mapear ni abrir en la app de mapas.
        """
        return bool(
            (self.lat is not None and self.lon is not None)
            or self.address
            or self.neighborhood
        )


@dataclass
class Event:
    title: str
    category: str
    date: str  # YYYY-MM-DD
    access_mode: str
    venue: Venue
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None
    all_day: bool = False
    reservation_url: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    updated_at: Optional[str] = None
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.stable_id()

    def stable_id(self) -> str:
        """Id determinista: la misma actividad conserva su id entre corridas.

        Eso permite que Room haga upsert sin duplicar filas y que los
        favoritos del usuario sobrevivan a la actualizacion diaria.
        """
        return f"{slugify(self.venue.id)}-{slugify(self.title)[:60]}-{self.date}"

    def to_dict(self) -> dict:
        data = asdict(self)
        # Orden estable de claves -> diffs limpios en git.
        ordered = {
            "id": data["id"],
            "title": data["title"],
            "description": data["description"],
            "category": data["category"],
            "tags": data["tags"],
            "date": data["date"],
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "all_day": data["all_day"],
            "access_mode": data["access_mode"],
            "reservation_url": data["reservation_url"],
            "venue": data["venue"],
            "source_name": data["source_name"],
            "source_url": data["source_url"],
            "image_url": data["image_url"],
            "updated_at": data["updated_at"],
        }
        return ordered
