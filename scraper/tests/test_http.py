"""Transporte: robots.txt, IPv4 y el fallback cuando falta curl_cffi.

Nada de esto toca la red: se le inyecta a `permitido` la función que trae la
URL, que es justamente por qué está parametrizada.
"""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventos import http  # noqa: E402
from eventos.http import PoliteSession, RobotsBloqueado, permitido  # noqa: E402
from eventos.registry import _transporte  # noqa: E402
from eventos.sources.base import Source  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_cache():
    http._robots_cache.clear()
    yield
    http._robots_cache.clear()


def _robots(texto: str, status: int = 200):
    return lambda url: Mock(status_code=status, text=texto)


# --- robots.txt ------------------------------------------------------------

def test_respeta_una_prohibicion_explicita():
    reglas = "User-agent: *\nDisallow: /agenda/\n"
    assert not permitido("https://sitio.ar/agenda/", _robots(reglas))
    assert permitido("https://sitio.ar/otra-cosa", _robots(reglas))


def test_sin_robots_txt_se_asume_permitido():
    """RFC 9309: un 4xx al pedir robots.txt es 'no hay reglas', no 'prohibido'."""
    assert permitido("https://sitio.ar/agenda/", _robots("", status=404))


def test_un_robots_que_no_se_puede_traer_no_nos_frena():
    def explota(url):
        raise ConnectionError("cae la red")

    assert permitido("https://sitio.ar/agenda/", explota)


def test_las_reglas_se_piden_una_sola_vez_por_dominio():
    trae = Mock(return_value=Mock(status_code=200, text="User-agent: *\n"))
    permitido("https://sitio.ar/a", trae)
    permitido("https://sitio.ar/b", trae)
    assert trae.call_count == 1


# --- la sesión -------------------------------------------------------------

def test_la_sesion_no_pide_lo_que_robots_prohibe():
    sesion = PoliteSession(impersonate=False)
    sesion._session = Mock()
    sesion._session.get.return_value = Mock(
        status_code=200, text="User-agent: *\nDisallow: /agenda/\n")
    with pytest.raises(RobotsBloqueado):
        sesion.get("https://sitio.ar/agenda/hoy")


def test_se_puede_apagar_el_chequeo_para_diagnosticar():
    """El diagnóstico necesita ver el 403 crudo del sitio, no frenarse solo."""
    sesion = PoliteSession(impersonate=False, respetar_robots=False)
    sesion._session = Mock()
    sesion._session.get.return_value = Mock(status_code=403, text="")
    assert sesion.get("https://sitio.ar/agenda/").status_code == 403


def test_forzar_ipv4_usa_requests_y_no_el_tls_de_navegador():
    """curl_cffi no puede forzar IPv4 vía urllib3, y ahí el problema es de red."""
    sesion = PoliteSession(impersonate=True, force_ipv4=True)
    assert sesion.transporte == "requests"
    assert sesion.force_ipv4


def test_sin_curl_cffi_sigue_funcionando(monkeypatch):
    monkeypatch.setattr(http, "curl_requests", None)
    sesion = PoliteSession(impersonate=True)
    assert sesion.transporte == "requests"


# --- el registro pasa las perillas de red ----------------------------------

def test_el_registro_aplica_force_ipv4_y_timeout():
    fuente = _transporte(Source(), {"force_ipv4": True, "timeout": 60})
    assert fuente.force_ipv4 and fuente.timeout == 60


def test_una_fuente_sin_pedidos_usa_la_sesion_compartida():
    compartida = object()
    assert Source()._session_propia(compartida) is compartida
