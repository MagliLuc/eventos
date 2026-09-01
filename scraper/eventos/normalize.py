"""Heuristicas de normalizacion: categoria, modalidad de ingreso, horarios.

Las agendas oficiales publican texto libre en castellano. Estas funciones
lo llevan a los enums que consume la app, para que el filtrado en el
telefono sea una comparacion exacta y no un `contains` frágil.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Orden importante: la primera categoria que matchea gana, por eso
# INFANTILES va antes que MUSICA (un "concierto para chicos" es infantil).
CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("INFANTILES", ("infantil", "infancias", "para chicos", "ninos", "familia",
                    "titeres", "juguete", "taller para")),
    ("CINE", ("cine", "film", "cortometraje", "largometraje", "proyeccion",
              "audiovisual", "documental", "animacion")),
    ("TEATRO", ("teatro", "danza", "obra", "performance", "escenica",
                "circo", "ballet", "coreograf")),
    ("ARTES_VISUALES", ("muestra", "exposicion", "exhibicion", "galeria",
                        "museo", "pintura", "escultura", "fotografia",
                        "instalacion", "artes visuales")),
    ("FERIAS", ("feria", "colectividad", "celebracion", "festejo", "mercado",
                "gastronom", "artesan", "aire libre", "parque", "plaza")),
    ("MUSICA", ("musica", "concierto", "recital", "orquesta", "coro",
                "milonga", "tango", "sinfonic", "camara", "jazz", "banda",
                "cantante", "dj")),
]

RESERVA_KEYWORDS = ("reserva", "inscripcion previa", "entrada previa",
                    "retirar entrada", "cupo limitado con reserva",
                    "ticket", "eventbrite")
ORDEN_KEYWORDS = ("orden de llegada", "hasta agotar", "por orden",
                  "sujeto a capacidad", "aforo", "capacidad de la sala")

# El punto separa horas ("18.30 h") pero tambien fechas ("Desde el 20.09"),
# que es como escribe su agenda el Centro Cultural Recoleta. Con los dos
# puntos no hay ambiguedad; con el punto se exige la "h" o "hs", porque si no
# una fecha entra como horario: "20.09" se leia como las 20:09.
TIME_RANGE_RE = re.compile(
    r"(\d{1,2})(?::(\d{2})|\.(\d{2})\s*(?:h|hs))\s*(?:h|hs)?"
    r"\s*(?:a|hasta|-|–|—)\s*(\d{1,2})(?::(\d{2})|\.(\d{2})\s*(?:h|hs))",
    re.IGNORECASE,
)
SINGLE_TIME_RE = re.compile(
    r"(\d{1,2})(?::(\d{2})\s*(?:h|hs)?|\.(\d{2})\s*(?:h|hs))", re.IGNORECASE)
BARE_HOUR_RE = re.compile(r"(?:^|\s)(\d{1,2})\s*(?:h|hs)\b", re.IGNORECASE)


def strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def detect_category(*texts: Optional[str]) -> str:
    """Clasifica en una de las categorias de la app a partir de texto libre."""
    haystack = strip_accents(" ".join(t for t in texts if t))
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "OTROS"


def detect_access_mode(*texts: Optional[str]) -> str:
    """Distingue reserva digital previa vs. orden de llegada vs. libre."""
    haystack = strip_accents(" ".join(t for t in texts if t))
    if any(keyword in haystack for keyword in RESERVA_KEYWORDS):
        return "RESERVA_PREVIA"
    if any(keyword in haystack for keyword in ORDEN_KEYWORDS):
        return "ORDEN_DE_LLEGADA"
    return "INGRESO_LIBRE"


def _clamp_time(hour: int, minute: int) -> Optional[str]:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def parse_times(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Extrae (inicio, fin) de textos como '14:00 a 17:00 h' o '19 hs'."""
    if not text:
        return None, None

    # Los minutos vienen por dos ramas alternativas (dos puntos o punto), asi
    # que se toma la que haya matcheado.
    def _minutos(*grupos: Optional[str]) -> int:
        return int(next((g for g in grupos if g is not None), 0))

    match = TIME_RANGE_RE.search(text)
    if match:
        start = _clamp_time(int(match.group(1)), _minutos(match.group(2), match.group(3)))
        end = _clamp_time(int(match.group(4)), _minutos(match.group(5), match.group(6)))
        if start:
            return start, end

    match = SINGLE_TIME_RE.search(text)
    if match:
        start = _clamp_time(int(match.group(1)), _minutos(match.group(2), match.group(3)))
        if start:
            return start, None

    match = BARE_HOUR_RE.search(text)
    if match:
        return _clamp_time(int(match.group(1)), 0), None

    return None, None


def is_free(*texts: Optional[str]) -> bool:
    """La app solo publica actividades gratuitas: este es el filtro final."""
    haystack = strip_accents(" ".join(t for t in texts if t))
    paid_markers = ("$", "precio", "valor de la entrada", "entrada general",
                    "arancel", "pago")
    free_markers = ("gratis", "gratuit", "entrada libre", "ingreso libre",
                    "acceso libre", "sin cargo", "libre y gratuit")
    if any(marker in haystack for marker in free_markers):
        return True
    return not any(marker in haystack for marker in paid_markers)


def is_explicitly_free(*texts: Optional[str]) -> bool:
    """Como `is_free`, pero exige que el texto lo diga.

    `is_free` acepta por defecto lo que no menciona precio, y esta bien para
    JSON-LD, donde el campo `offers` ya dice cuanto sale. Cuando la fuente es
    prosa de una nota periodistica no hay tal campo: ahi el silencio no
    significa gratis, asi que se exige la palabra.
    """
    haystack = strip_accents(" ".join(t for t in texts if t))
    # "libre" solo no alcanza ("aire libre", "libre albedrio"), pero varias
    # salas escriben "Actividad libre" o "Asistencia libre" y sin esos giros
    # se descartaban eventos que si eran gratuitos: Fundacion Proa, por caso.
    return any(marker in haystack for marker in
               ("gratis", "gratuit", "entrada libre", "ingreso libre",
                "acceso libre", "actividad libre", "asistencia libre",
                "participacion libre", "entrada gratuita", "sin cargo"))


def clean_text(text: Optional[str], limit: int = 400) -> Optional[str]:
    """Colapsa espacios y recorta descripciones largas del HTML original."""
    if not text:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed:
        return None
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "…"
    return collapsed
