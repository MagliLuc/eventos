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


# --- Prospección: no gastar una hora en un dominio inventado --------------

def test_un_host_caido_se_descarta_antes_de_sondear():
    """Sin este corte, un dominio que traga paquetes cuesta ~15 minutos.

    Cada mecanismo sondea entre 1 y 12 rutas con timeouts de 20-30 s. Con
    once candidatas municipales de URL conjeturada, eso convirtió una
    prospección de veinte minutos en una de más de una hora.
    """
    import discover

    class SesionQueFalla:
        pedidos = 0

        def get(self, url, **kwargs):
            SesionQueFalla.pedidos += 1
            raise OSError("sin ruta al host")

    ses = SesionQueFalla()
    assert discover.revisar_compacto(ses, {"name": "Inventada",
                                           "url": "https://no-existe.test/cultura"}) is None
    # Un solo pedido, no los treinta y pico de los ocho mecanismos.
    assert SesionQueFalla.pedidos == 1


# --- El filtro geográfico: eventos de Córdoba en una app del AMBA ---------

def test_el_pipeline_descarta_lo_que_esta_fuera_del_amba():
    """Ejercita `run()` de punta a punta, no sólo el predicado.

    La primera versión de esto usaba `fuera_del_amba` sin importarlo en
    `pipeline.py`: los tests del predicado pasaban igual y el pipeline
    reventaba recién en la corrida.
    """
    import tempfile
    from pathlib import Path

    from eventos.models import DateWindow, Event, Venue, slugify, today_ba
    from eventos.pipeline import run
    from eventos.sources.base import Source

    hoy = today_ba()

    def evento(titulo, direccion):
        return Event(title=titulo, category="MUSICA", date=hoy.isoformat(),
                     access_mode="INGRESO_LIBRE",
                     venue=Venue(id=slugify(titulo), name=titulo, address=direccion))

    class FuenteNacional(Source):
        name = "Fuente nacional"

        def fetch(self, session, window: DateWindow):
            return [
                evento("Recital porteño", "Av. Corrientes 1660 - Capital Federal - Buenos Aires"),
                evento("Recital cordobés", "Cruz Roja Argentina 200 - Córdoba - Córdoba"),
                evento("Recital marplatense", "Bv. Marítimo 2280 - Mar del Plata - Buenos Aires"),
            ]

    with tempfile.TemporaryDirectory() as tmp:
        payload = run(Path(tmp) / "out.json", days=7, sources=[FuenteNacional()],
                      include_seed=False, keep_existing=False)

    titulos = [e["title"] for e in payload["events"]]
    assert titulos == ["Recital porteño"], titulos


def test_ante_la_duda_el_filtro_deja_pasar():
    """Una dirección sin jurisdicción escrita no se descarta."""
    from eventos.models import Venue
    from eventos.venues import fuera_del_amba

    assert fuera_del_amba(Venue(id="x", name="X", address="Av. San Juan 350")) is None
    assert fuera_del_amba(Venue(id="x", name="X", address=None)) is None


def test_el_filtro_no_confunde_una_calle_con_una_provincia():
    """El barrido por palabras marcaba 37 eventos buenos; éste, ninguno."""
    from eventos.models import Venue
    from eventos.venues import fuera_del_amba

    for direccion in ("Av. San Juan 350",
                      "Av. Corrientes 1660 - Capital Federal - Buenos Aires",
                      "Posadas 1557 - Recoleta - Ciudad de Buenos Aires",
                      "Paraná 353 - Capital Federal - Buenos Aires"):
        assert fuera_del_amba(Venue(id="x", name="X", address=direccion)) is None, direccion


# --- El precio declarado en offers ----------------------------------------

def test_un_evento_con_precio_no_es_gratuito():
    """`_de_jsonld` ignoraba `offers` por completo.

    Así entraron dos recitales pagos de Córdoba: su descripción no menciona
    plata, y el precio estaba en un campo que esa rama no miraba.
    """
    from eventos.sources.base import oferta_de, tiene_precio

    precio, texto = oferta_de({"offers": {"price": "25000", "name": "Entrada general"}})
    assert precio == "25000"
    assert tiene_precio(precio)
    assert "Entrada general" in texto


def test_un_precio_en_cero_sigue_siendo_gratuito():
    from eventos.sources.base import oferta_de, tiene_precio

    for cero in ("0", "0.0", "0.00", "0,00", ""):
        assert not tiene_precio(cero), cero


def test_offers_como_lista_o_ausente_no_rompe():
    from eventos.sources.base import oferta_de

    assert oferta_de({"offers": [{"price": "500"}]})[0] == "500"
    assert oferta_de({}) == ("", "")
    assert oferta_de({"offers": None}) == ("", "")
    assert oferta_de({"offers": "gratis"}) == ("", "")


def test_las_dos_ramas_jsonld_usan_el_mismo_chequeo():
    """La duplicación era la causa: una miraba el precio y la otra no."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "eventos" / "sources"
    for archivo in ("feeds.py", "html_source.py"):
        texto = (raiz / archivo).read_text(encoding="utf-8")
        assert "tiene_precio(" in texto, archivo


# --- La hora de fin que no era dato ---------------------------------------

def test_ignorar_hora_fin_borra_solo_el_fin():
    """Qué Hacemos publicaba inicio + exactamente 6 h en los 22 eventos.

    Con inicios variados (20:00, 10:00, 15:14) esa uniformidad no es dato:
    es relleno del sitio, y lo estábamos mostrando como el horario del show.
    """
    from eventos.models import DateWindow
    from eventos.sources.feeds import FichasSource

    nodo = {
        "@type": "Event", "name": "Recital",
        "startDate": "2026-09-05T20:00", "endDate": "2026-09-06T02:00",
        "description": "Entrada libre y gratuita",
        "location": {"name": "Sala X", "address": "Calle 1 - Almagro - CABA"},
    }
    ventana = DateWindow.upcoming(21)

    fuente = FichasSource("X", "https://x.test/", "Sala X")
    normal = fuente._de_jsonld(nodo, ventana, "https://x.test/f")
    assert (normal.start_time, normal.end_time) == ("20:00", "02:00")

    fuente.ignorar_hora_fin = True
    recortado = fuente._de_jsonld(nodo, ventana, "https://x.test/f")
    assert recortado.start_time == "20:00", "el inicio no se toca"
    assert recortado.end_time is None


def test_el_registro_aplica_ignorar_hora_fin():
    from eventos.registry import _construir, _transporte

    entrada = {"name": "Qué Hacemos", "kind": "fichas", "status": "activo",
               "url": "https://x.test/eventos-gratis", "venue": "CABA",
               "ignorar_hora_fin": True}
    assert _transporte(_construir(entrada), entrada).ignorar_hora_fin is True


def test_una_fuente_normal_conserva_su_hora_de_fin():
    from eventos.registry import _construir, _transporte

    entrada = {"name": "Museo Moderno", "kind": "fichas", "status": "activo",
               "url": "https://x.test/agenda", "venue": "Museo Moderno"}
    assert _transporte(_construir(entrada), entrada).ignorar_hora_fin is False


# --- El prospector proponía un feed de comentarios como agenda ------------

def test_el_feed_de_comentarios_no_es_una_agenda():
    """WordPress declara dos feeds en el <head>: entradas y comentarios.

    Ordenados alfabéticamente gana "comments/feed", y como parsea igual de
    bien, la prospección del 2026-09-01 propuso el feed de COMENTARIOS de la
    Usina como fuente de eventos. Pegar esa configuración habría publicado
    comentarios de blog como si fueran la agenda.
    """
    from discover import es_feed_de_comentarios

    assert es_feed_de_comentarios("https://usinadelarte.ar/comments/feed/")
    assert es_feed_de_comentarios("https://x.ar/comments/feed")
    assert not es_feed_de_comentarios("https://usinadelarte.ar/feed/")
    assert not es_feed_de_comentarios("https://museomoderno.org/agenda/feed/")
