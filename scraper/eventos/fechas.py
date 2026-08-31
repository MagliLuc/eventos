"""Fechas escritas en castellano, ancladas al texto.

Teatro Colón y Usina del Arte publican feeds con diez notas cada uno y hoy
rinden cero eventos: las notas no traen JSON-LD, así que no hay `startDate`
que leer. La fecha *está* en el texto ("Sábado 6 de septiembre, 18 h"), solo
que en prosa.

La regla que no se negocia: **la fecha tiene que estar escrita en el texto**.
Nada de resolver "este finde" o "el próximo jueves" contra el día de la
corrida — así fue como una versión anterior del scraper terminó clonando el
mismo evento con siete fechas distintas. Si no hay una fecha literal, la
entrada se descarta.

Por eso esto se hace con expresiones regulares y no con `dateparser`: la
gracia de `dateparser` es justamente inferir fechas relativas a hoy, que es lo
que acá queremos prohibir. Y de paso no suma una dependencia.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

from .models import DateWindow
from .normalize import strip_accents

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_NOMBRES = "|".join(MESES)

# "del 5 al 20 de septiembre", "5 al 20 de septiembre de 2026"
RANGO_RE = re.compile(
    rf"\b(?:del\s+|desde\s+el\s+)?(\d{{1,2}})\s*(?:al|a|hasta\s+el)\s*(\d{{1,2}})"
    rf"\s+de\s+({_NOMBRES})(?:\s+de\s+(\d{{4}}))?", re.IGNORECASE)

# "sábado 6 de septiembre", "6 de septiembre de 2026"
DIA_MES_RE = re.compile(
    rf"\b(\d{{1,2}})\s+de\s+({_NOMBRES})(?:\s+de\s+(\d{{4}}))?", re.IGNORECASE)

# "06/09", "06/09/2026" — se lee día/mes, que es como se escribe acá
BARRAS_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

MAX_DIAS = 40  # tope de un rango: una muestra larga no debe inundar la agenda


def _distancia(valor: date, window: DateWindow) -> int:
    if valor < window.start:
        return (window.start - valor).days
    if valor > window.end:
        return (valor - window.end).days
    return 0


def _armar(dia: int, mes: int, anio: Optional[int],
           window: DateWindow) -> Optional[date]:
    """Construye la fecha; sin año, elige el más cercano a la ventana.

    Ojo con no exigir que caiga *dentro* de la ventana acá: una muestra "del 5
    al 20 de septiembre" arranca antes de hoy y sigue abierta, y descartar el
    5 por estar fuera perdería el rango entero. El recorte a la ventana lo
    hace quien llama, que ya tiene el rango completo.
    """
    candidatos = [anio] if anio else [window.start.year - 1, window.start.year,
                                      window.start.year + 1]
    posibles: list[date] = []
    for posible in candidatos:
        try:
            posibles.append(date(posible, mes, dia))
        except ValueError:
            continue
    if not posibles:
        return None
    return min(posibles, key=lambda v: _distancia(v, window))


def _mes(nombre: str) -> int:
    return MESES[strip_accents(nombre).lower()]


def extraer_fechas(texto: Optional[str], window: DateWindow) -> list[str]:
    """Fechas ISO literales del texto que caen dentro de la ventana.

    Devuelve lista porque un rango ("del 5 al 20 de septiembre") es una
    muestra que está abierta todos esos días: cada día es un evento con su
    propio id estable, igual que hace la semilla curada.
    """
    if not texto:
        return []
    plano = strip_accents(texto)
    encontradas: list[date] = []

    for dia_i, dia_f, mes, anio in RANGO_RE.findall(plano):
        numero_mes = _mes(mes)
        explicito = int(anio) if anio else None
        fin = _armar(int(dia_f), numero_mes, explicito, window)
        if int(dia_i) <= int(dia_f):
            inicio = _armar(int(dia_i), numero_mes, explicito, window)
        else:
            # "del 28 al 5 de septiembre": el mes escrito es el del final, el
            # arranque es del mes anterior. Pasa seguido en muestras largas y
            # descartarlo perdía el rango entero.
            inicio = _armar(int(dia_i), 12 if numero_mes == 1 else numero_mes - 1,
                            (explicito - 1) if explicito and numero_mes == 1
                            else explicito, window)
        if not inicio or not fin or fin < inicio:
            continue
        desde, hasta = max(inicio, window.start), min(fin, window.end)
        dia = desde
        while dia <= hasta and len(encontradas) < MAX_DIAS:
            encontradas.append(dia)
            dia += timedelta(days=1)

    for dia, mes, anio in DIA_MES_RE.findall(plano):
        valor = _armar(int(dia), _mes(mes), int(anio) if anio else None, window)
        if valor:
            encontradas.append(valor)

    for dia, mes, anio in BARRAS_RE.findall(plano):
        if not 1 <= int(mes) <= 12:
            continue
        completo = int(anio) + 2000 if anio and len(anio) == 2 else (int(anio) if anio else None)
        valor = _armar(int(dia), int(mes), completo, window)
        if valor:
            encontradas.append(valor)

    for anio, mes, dia in ISO_RE.findall(plano):
        try:
            encontradas.append(date(int(anio), int(mes), int(dia)))
        except ValueError:
            continue

    dentro = sorted({d for d in encontradas if window.start <= d <= window.end})
    return [d.isoformat() for d in dentro[:MAX_DIAS]]


def extraer_fecha(texto: Optional[str], window: DateWindow) -> Optional[str]:
    """La primera fecha literal del texto dentro de la ventana, o None."""
    fechas = extraer_fechas(texto, window)
    return fechas[0] if fechas else None
