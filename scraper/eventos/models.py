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

# Como se paga, que es un eje distinto de como se entra.
#
# "A la gorra" no es un modo de acceso: se entra igual que a cualquier
# funcion libre, y la plata se aporta al final. Tanto es asi que una funcion
# puede ser a la gorra *y* con reserva previa. Metido en ACCESS_MODES, uno de
# los dos datos se perderia.
CONTRIBUTIONS = ("A_LA_GORRA",)

# Zonas del AMBA. El corte no es caprichoso: son los accesos que la gente
# usa para moverse (Norte por el Mitre y Panamericana, Oeste por el Sarmiento
# y el Acceso Oeste, Sur por el Roca y la Riccheri), asi que "Conurbano
# Norte" contesta la pregunta real, que es cuanto me cuesta llegar.
ZONES = ("CABA", "CONURBANO_NORTE", "CONURBANO_SUR", "CONURBANO_OESTE")

# Partido -> zona. Es el mapa que convierte una localidad suelta en algo
# filtrable; lo consume `venues.zona_de_partido`.
PARTIDOS_POR_ZONA: dict[str, tuple[str, ...]] = {
    "CONURBANO_NORTE": (
        "Vicente López", "San Isidro", "San Fernando", "Tigre",
        "General San Martín", "Tres de Febrero", "San Miguel",
        "José C. Paz", "Malvinas Argentinas", "Escobar", "Pilar",
    ),
    "CONURBANO_OESTE": (
        "Morón", "La Matanza", "Merlo", "Moreno", "Ituzaingó", "Hurlingham",
        "Marcos Paz", "General Rodríguez", "Luján",
    ),
    "CONURBANO_SUR": (
        "Avellaneda", "Lanús", "Lomas de Zamora", "Quilmes", "Berazategui",
        "Florencio Varela", "Almirante Brown", "Esteban Echeverría",
        "Ezeiza", "San Vicente", "Presidente Perón", "La Plata",
        "Berisso", "Ensenada",
    ),
}


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
    # Barrio en CABA, localidad en el Conurbano. Es el mismo rol -- el nivel
    # fino de la geografia -- asi que va en un solo campo: dos campos
    # paralelos serian dos lugares donde olvidarse de mirar el otro.
    neighborhood: Optional[str] = None
    # Dato de CABA y solo de CABA: fuera de la Ciudad no existen las comunas.
    commune: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    # Nivel grueso de la geografia. Por defecto CABA para que las sedes que
    # ya estaban no cambien de significado al sumarse este campo.
    zone: str = "CABA"

    @property
    def in_caba(self) -> bool:
        return self.zone == "CABA"

    @property
    def locality(self) -> str:
        """Como se nombra la jurisdiccion al final de una direccion.

        Existe para que nadie vuelva a escribir ", CABA" a mano: eso mandaba
        a quien tocara "Como llegar" a una direccion de Capital aunque el
        evento fuera en San Isidro.
        """
        return "CABA" if self.in_caba else "Provincia de Buenos Aires"

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
    # Quien PRODUJO el evento, aparte del nombre humano. Hacen falta los dos:
    # la semilla curada publica eventos con source_name "Centro Cultural
    # Recoleta", igual que la fuente en vivo homonima, y sin este id el panel
    # de la app mostraria el estado del scraper sobre eventos que no salieron
    # de ahi. Lo estampa el pipeline, no cada fuente.
    source_id: Optional[str] = None
    # "A_LA_GORRA" o None. Va aparte de access_mode porque son ejes
    # distintos: uno dice como se entra, este dice como se paga.
    contribution: Optional[str] = None
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
            "contribution": data["contribution"],
            "reservation_url": data["reservation_url"],
            "venue": data["venue"],
            "source_name": data["source_name"],
            "source_url": data["source_url"],
            "source_id": data["source_id"],
            "image_url": data["image_url"],
            "updated_at": data["updated_at"],
        }
        return ordered
