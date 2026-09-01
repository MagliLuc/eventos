"""Estado de cada fuente, para que la app lo pueda mostrar.

Esta información ya existía: el contador de motivos de `_leer_fichas` venía
diciendo «18 con evento, 6 sin fecha escrita, 6 sin decir que sean gratis»
desde hace varias corridas. Pero se imprimía en el log de CI y moría ahí, así
que la única forma de saber si una fuente seguía andando era leer los logs.
Acá se convierte en un dato que viaja en `events.json`.

La distinción que importa, y por la que hay cuatro estados y no dos:

  INCOMPLETA  es un problema NUESTRO: la fuente publica actividades que no
              logramos leer (sin título legible, sin fecha que podamos anclar).
  SIN_EVENTOS es el resultado CORRECTO: la fuente anda y hoy no tiene nada
              gratuito. El Teatro Colón vende entradas; que devuelva cero no
              es una falla que haya que ir a arreglar.

Confundirlas manda a perder tiempo arreglando lo que funciona, o a ignorar lo
que se rompió.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Estados, del mejor al peor. El orden es el que usa el panel para listar.
OK = "OK"
INCOMPLETA = "INCOMPLETA"
SIN_EVENTOS = "SIN_EVENTOS"
ERROR = "ERROR"

ESTADOS = (OK, INCOMPLETA, SIN_EVENTOS, ERROR)

# Motivos por los que se descarta una ficha. Los dos primeros son corregibles
# (nos falta leer mejor); el tercero es una decisión legítima del filtro.
CORREGIBLES = ("titulo", "fecha")

# A partir de acá una fuente se considera incompleta. No es un número mágico:
# por debajo de un tercio, descartar fichas es lo normal (una agenda mezcla
# actividades pagas, pasadas y avisos); por encima, estamos perdiendo datos.
UMBRAL_INCOMPLETA = 0.30


@dataclass
class InformeFuente:
    """Cómo le fue a una fuente en esta corrida."""

    id: str
    nombre: str
    eventos: int = 0
    fichas: int = 0
    motivos: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    url: Optional[str] = None

    @property
    def descartadas_corregibles(self) -> int:
        return sum(self.motivos.get(m, 0) for m in CORREGIBLES)

    @property
    def estado(self) -> str:
        if self.error:
            return ERROR
        # Ni un evento ni una ficha leída: no llegamos al sitio, o cambió tanto
        # que no encontramos por dónde entrar.
        if self.eventos == 0 and self.fichas == 0:
            return ERROR
        if self.eventos == 0:
            return SIN_EVENTOS
        if self.fichas and self.descartadas_corregibles / self.fichas >= UMBRAL_INCOMPLETA:
            return INCOMPLETA
        return OK

    @property
    def detalle(self) -> str:
        """Una línea, en castellano, explicando el estado.

        La escribe el scraper y no la app porque acá están los números; la app
        solo la muestra. Si mañana cambia el criterio, cambia en un solo lado.
        """
        if self.error:
            return self.error
        if self.eventos == 0 and self.fichas == 0:
            return "No se pudo leer ninguna actividad del sitio."

        partes = []
        if self.motivos.get("precio"):
            partes.append(f"{self.motivos['precio']} no dicen ser gratuitas")
        if self.motivos.get("fecha"):
            partes.append(f"{self.motivos['fecha']} sin fecha legible")
        if self.motivos.get("titulo"):
            partes.append(f"{self.motivos['titulo']} sin título legible")
        detalle_descartes = "; ".join(partes)

        if self.eventos == 0:
            return (f"El sitio responde, pero de {self.fichas} actividades "
                    f"ninguna es gratuita ahora"
                    + (f" ({detalle_descartes})." if detalle_descartes else "."))
        base = f"{self.eventos} eventos de {self.fichas} actividades leídas"
        return f"{base} ({detalle_descartes})." if detalle_descartes else f"{base}."

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.nombre,
            "url": self.url,
            "status": self.estado,
            "detail": self.detalle,
            "events": self.eventos,
            "items_read": self.fichas,
            "discarded": {k: v for k, v in sorted(self.motivos.items()) if k != "ok"},
        }
