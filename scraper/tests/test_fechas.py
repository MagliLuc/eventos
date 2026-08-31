"""Fechas en castellano: lo que importa es lo que NO se acepta.

El bug que motivó estas reglas: una versión anterior asumía la fecha pedida
cuando el HTML no traía una legible, y como el pipeline llamaba a cada fuente
una vez por día, el mismo evento terminaba publicado siete veces con siete
fechas. De ahí la invariante: si la fecha no está escrita, no hay evento.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.fechas import extraer_fecha, extraer_fechas  # noqa: E402
from eventos.models import DateWindow  # noqa: E402

VENTANA = DateWindow(start=date(2026, 9, 1), end=date(2026, 9, 28))


@pytest.mark.parametrize("texto, esperado", [
    ("Sábado 6 de septiembre a las 18 h", "2026-09-06"),
    ("sabado 6 de setiembre", "2026-09-06"),          # sin tilde y variante
    ("Función el 20 de septiembre de 2026", "2026-09-20"),
    ("Concierto el 20/09 a las 20:30", "2026-09-20"),
    ("Cierra el 2026-09-15", "2026-09-15"),
])
def test_reconoce_fechas_escritas(texto, esperado):
    assert extraer_fecha(texto, VENTANA) == esperado


@pytest.mark.parametrize("texto", [
    "Se presenta el próximo sábado",
    "Todos los fines de semana de este mes",
    "Ya está abierta la inscripción",
    "",
    None,
])
def test_no_inventa_fechas_relativas(texto):
    """Sin fecha literal no hay evento: esto es la regla, no un detalle."""
    assert extraer_fechas(texto, VENTANA) == []


def test_descarta_lo_que_cae_fuera_de_la_ventana():
    assert extraer_fechas("Función el 3 de marzo de 2020", VENTANA) == []
    assert extraer_fechas("Estreno el 15 de diciembre de 2026", VENTANA) == []


def test_un_rango_es_un_evento_por_dia():
    """Una muestra abierta del 5 al 8 se puede visitar los cuatro días."""
    assert extraer_fechas("Puede visitarse del 5 al 8 de septiembre", VENTANA) == [
        "2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08",
    ]


def test_un_rango_que_arranco_antes_se_recorta_a_la_ventana():
    """Una muestra que empezó antes y sigue abierta no se pierde."""
    ventana = DateWindow(start=date(2026, 9, 3), end=date(2026, 9, 10))
    fechas = extraer_fechas("Abierta del 1 al 5 de septiembre", ventana)
    assert fechas == ["2026-09-03", "2026-09-04", "2026-09-05"]


def test_un_rango_puede_cruzar_de_mes():
    """'del 28 al 5 de septiembre' arranca el 28 de agosto, no el 28/09."""
    ventana = DateWindow(start=date(2026, 8, 30), end=date(2026, 9, 3))
    assert extraer_fechas("Del 28 al 5 de septiembre", ventana) == [
        "2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03",
    ]


def test_sin_anio_elige_el_que_corresponde_a_la_ventana():
    """Fin de año: 'el 3 de enero' es del año siguiente, no del que corre."""
    ventana = DateWindow(start=date(2026, 12, 28), end=date(2027, 1, 10))
    assert extraer_fecha("Concierto el 3 de enero", ventana) == "2027-01-03"


def test_ignora_dias_y_meses_imposibles():
    assert extraer_fechas("el 31/02 y el 45 de septiembre", VENTANA) == []


def test_no_devuelve_duplicados():
    texto = "El 6 de septiembre. Repetimos: 6 de septiembre, 06/09."
    assert extraer_fechas(texto, VENTANA) == ["2026-09-06"]
