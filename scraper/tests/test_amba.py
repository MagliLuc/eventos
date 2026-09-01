"""Tests de la ampliación al AMBA: zona, dirección y «a la gorra».

Corren sin red, igual que el resto: `python -m pytest scraper/tests`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos.models import PARTIDOS_POR_ZONA, ZONES, Venue  # noqa: E402
from eventos.normalize import (  # noqa: E402
    detect_access_mode,
    detect_contribution,
    is_explicitly_free,
)
from eventos.venues import (  # noqa: E402
    KNOWN_VENUES,
    build_venue,
    contexto_geografico,
    zona_de_partido,
)


# --- Zona -----------------------------------------------------------------

def test_las_sedes_conocidas_son_todas_de_caba():
    # Las del Conurbano se agregan cuando la prospección apruebe su fuente y
    # su propio HTML dé la dirección. Si alguna aparece acá sin ese paso, es
    # que se escribió de memoria, que es justo lo que el proyecto no hace.
    assert {s.zone for s in KNOWN_VENUES.values()} == {"CABA"}


def test_toda_zona_declarada_existe():
    assert set(PARTIDOS_POR_ZONA) <= set(ZONES)


def test_ningun_partido_esta_en_dos_zonas():
    todos = [p for partidos in PARTIDOS_POR_ZONA.values() for p in partidos]
    assert len(todos) == len(set(todos))


def test_zona_de_partido_reconoce_los_tres_cordones():
    assert zona_de_partido("San Isidro") == "CONURBANO_NORTE"
    assert zona_de_partido("Quilmes") == "CONURBANO_SUR"
    assert zona_de_partido("La Matanza") == "CONURBANO_OESTE"


def test_zona_de_partido_tolera_acentos_y_mayusculas():
    assert zona_de_partido("morón") == "CONURBANO_OESTE"
    assert zona_de_partido("MORON") == "CONURBANO_OESTE"


def test_lo_que_no_es_partido_cae_en_caba():
    assert zona_de_partido(None) == "CABA"
    assert zona_de_partido("Palermo") == "CABA"


def test_no_se_infiere_el_partido_desde_una_direccion():
    """La calle "Vicente López" no convierte una sede en el partido homónimo.

    Es una colisión real de nuestros propios datos: "Vicente López 2220" es
    la dirección del Museo Roca, en Recoleta. Por eso `zona_de_partido`
    recibe un partido declarado y no prosa.
    """
    sede = build_venue("Museo Roca")
    assert sede.zone == "CABA"
    assert sede.address == "Vicente López 2220"


# --- La dirección, que es el bug que motivó todo --------------------------

def test_una_sede_del_conurbano_no_dice_caba():
    sede = Venue(id="x", name="Sala", address="Av. Mitre 500",
                 neighborhood="Avellaneda", zone="CONURBANO_SUR")
    assert sede.locality == "Provincia de Buenos Aires"


def test_una_sede_de_caba_sigue_diciendo_caba():
    assert build_venue("Teatro Colón").locality == "CABA"


def test_el_contexto_de_geocodificacion_lleva_el_partido():
    # Sin esto, "Av. Mitre 500" del Conurbano se geocodificaba contra la
    # calle homónima de Capital: una coordenada equivocada manda a alguien
    # al lugar equivocado, que es peor que no tener coordenada.
    assert contexto_geografico("CABA") == "Ciudad Autónoma de Buenos Aires, Argentina"
    assert contexto_geografico("CONURBANO_NORTE", "San Isidro") == (
        "San Isidro, Provincia de Buenos Aires, Argentina"
    )


def test_una_sede_nueva_del_conurbano_es_ubicable_por_su_localidad():
    # Sin `neighborhood`, `is_locatable` la rechaza y el pipeline tira sus
    # eventos en silencio: es exactamente lo que pasó con el Museo Moderno.
    sede = build_venue("Centro Cultural X", locality="Quilmes")
    assert sede.zone == "CONURBANO_SUR"
    assert sede.neighborhood == "Quilmes"
    assert sede.is_locatable


def test_el_catalogo_manda_sobre_la_localidad_declarada():
    # Si la fuente se equivoca de partido, la sede conocida no se mueve.
    sede = build_venue("Teatro Colón", locality="Quilmes")
    assert sede.zone == "CABA"
    assert sede.neighborhood == "San Nicolás"


# --- A la gorra -----------------------------------------------------------

def test_a_la_gorra_se_detecta():
    assert detect_contribution("Función a la gorra") == "A_LA_GORRA"
    assert detect_contribution("Bono contribución $2000") == "A_LA_GORRA"
    assert detect_contribution("Entrada libre y gratuita") is None


def test_gorra_a_secas_no_alcanza():
    # Una obra puede llamarse "La gorra"; se exige el giro completo.
    assert detect_contribution("La gorra, de Juan Pérez") is None


def test_a_la_gorra_califica_como_gratuito():
    # Si se descartara acá, se perdería buena parte del teatro independiente
    # del AMBA sin que nadie se entere.
    assert is_explicitly_free("Teatro independiente, a la gorra")


def test_a_la_gorra_y_reserva_previa_conviven():
    """El caso que se perdería si fuera un valor más de ACCESS_MODES."""
    texto = "Función a la gorra. Requiere reserva previa."
    assert detect_access_mode(texto) == "RESERVA_PREVIA"
    assert detect_contribution(texto) == "A_LA_GORRA"


def test_el_silencio_sigue_sin_significar_gratis():
    # La regla vieja no se aflojó al sumar la gorra.
    assert not is_explicitly_free("Gran concierto de la orquesta")


# --- El partido declarado en el registro ----------------------------------

def test_una_fuente_del_conurbano_publica_en_su_zona():
    """La pieza que conecta `sources.json` con la zona del evento.

    Sin esto, una fuente de Quilmes publicaba sus eventos como si fueran de
    CABA y «Cómo llegar» mandaba a la calle homónima de Capital.
    """
    from eventos.registry import _construir

    fuente = _construir({
        "name": "Cultura Quilmes", "kind": "fichas",
        "url": "https://ejemplo.test/cultura", "venue": "Quilmes",
        "partido": "Quilmes", "status": "candidato",
    })
    fuente.partido = "Quilmes"
    sede = build_venue(fuente.default_venue, locality=fuente.partido)
    assert sede.zone == "CONURBANO_SUR"
    assert sede.locality == "Provincia de Buenos Aires"


def test_el_registro_aplica_el_partido():
    from eventos.registry import _construir, _transporte

    entrada = {
        "name": "Cultura San Isidro", "kind": "fichas",
        "url": "https://ejemplo.test/cultura", "venue": "San Isidro",
        "partido": "San Isidro", "status": "candidato",
    }
    fuente = _transporte(_construir(entrada), entrada)
    assert fuente.partido == "San Isidro"


def test_una_fuente_sin_partido_sigue_siendo_de_caba():
    from eventos.registry import _construir, _transporte

    entrada = {
        "name": "Museo Moderno", "kind": "fichas",
        "url": "https://ejemplo.test/agenda", "venue": "Museo Moderno",
        "status": "activo",
    }
    fuente = _transporte(_construir(entrada), entrada)
    assert fuente.partido is None
    assert build_venue(fuente.default_venue, locality=fuente.partido).zone == "CABA"


def test_todo_partido_declarado_en_el_registro_es_conocido():
    """Un partido mal escrito caería silenciosamente en CABA."""
    import json
    from pathlib import Path

    registro = json.loads(
        (Path(__file__).resolve().parents[1] / "sources.json").read_text(encoding="utf-8"))
    for entrada in registro["sources"]:
        partido = entrada.get("partido")
        if partido:
            assert zona_de_partido(partido) != "CABA", (
                f"'{entrada['name']}' declara el partido '{partido}', que no está "
                f"en PARTIDOS_POR_ZONA: sus eventos saldrían marcados como CABA."
            )
