"""Transporte HTTP: identificación, robots.txt, TLS de navegador e IPv4.

Por qué existe este módulo aparte de `sources/base.py`: los cuatro sitios
`.gob.ar` de la agenda devuelven 403 aun mandando las diez cabeceras de un
Chrome real. La explicación que queda es que el WAF no está mirando las
cabeceras sino el *handshake TLS*: el ClientHello de `requests`/OpenSSL tiene
un orden de cifrados y extensiones (el "JA3") idéntico en millones de bots y
distinto al de cualquier navegador, y el filtro decide antes de que la
petición llegue a la capa HTTP. Por eso arreglar cabeceras no movió la aguja.

`curl_cffi` reproduce el stack TLS de Chrome (cifrados, extensiones y el frame
SETTINGS de HTTP/2). Se usa si está instalado y se cae a `requests` si no, así
que el scraper sigue corriendo aunque la dependencia falte.

Dos límites que nos ponemos, y no son decorativos:

  * `robots.txt` manda. Si el sitio nos prohíbe la ruta, no se pide. Un 4xx al
    pedir robots.txt se interpreta como "no hay reglas" (RFC 9309).
  * Seguimos identificados: `From` y el User-Agent llevan la URL del proyecto,
    así que quien administre el sitio sabe quiénes somos y cómo frenarnos.

Son páginas públicas y el volumen es un puñado de pedidos por día.
"""
from __future__ import annotations

import socket
import threading
import time
import urllib.robotparser
from contextlib import contextmanager
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

try:  # opcional: si no está, se usa requests y se avisa una vez
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - depende del entorno
    curl_requests = None

CONTACTO = "https://github.com/MagliLuc/eventos"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/125.0.0.0 Safari/537.36 (+{CONTACTO}; agenda cultural gratuita)"
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "From": CONTACTO,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Perfil de curl_cffi. "chrome" apunta siempre a la última versión soportada
# por la librería instalada, así no queda clavado a un build viejo.
PERFIL_TLS = "chrome"


def hay_tls_de_navegador() -> bool:
    return curl_requests is not None


# ---------------------------------------------------------------------------
# IPv4 forzado
# ---------------------------------------------------------------------------
# Un ConnectTimeout que no es caída del sitio suele ser esto: el dominio tiene
# registro AAAA, el runner lo prefiere y no tiene ruta IPv6 real, así que el
# intento cuelga hasta agotar el timeout sin llegar a probar IPv4.

_lock_ipv4 = threading.Lock()

# ---------------------------------------------------------------------------
# Ritmo por dominio
# ---------------------------------------------------------------------------
# El primer diagnóstico se ganó un HTTP 429 de MALBA él solito: le pegó cuatro
# veces seguidas (robots + tres transportes) en menos de un segundo. Un 429 no
# dice nada del sitio, dice que fuimos maleducados. Un intervalo mínimo por
# host lo evita y de paso es la forma correcta de tratar a un servidor ajeno.

PAUSA_POR_HOST = 1.5  # segundos

_ultimo_pedido: dict[str, float] = {}
_lock_ritmo = threading.Lock()


def _esperar_turno(url: str) -> None:
    host = urlparse(url).netloc
    with _lock_ritmo:
        desde = time.monotonic() - _ultimo_pedido.get(host, 0.0)
        if desde < PAUSA_POR_HOST:
            time.sleep(PAUSA_POR_HOST - desde)
        _ultimo_pedido[host] = time.monotonic()


@contextmanager
def solo_ipv4():
    """Fuerza IPv4 en urllib3 mientras dure el bloque."""
    import urllib3.util.connection as conexion

    with _lock_ipv4:
        original = conexion.allowed_gai_family
        conexion.allowed_gai_family = lambda: socket.AF_INET
        try:
            yield
        finally:
            conexion.allowed_gai_family = original


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

_robots_cache: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}


def _base(url: str) -> str:
    partes = urlparse(url)
    return f"{partes.scheme}://{partes.netloc}"


def _robots(base: str, fetch) -> Optional[urllib.robotparser.RobotFileParser]:
    """Devuelve el parser de robots.txt del dominio, o None si no hay reglas.

    `fetch` es la función que trae la URL; se pasa desde afuera para que el
    pedido de robots.txt use el mismo transporte que el resto (si el sitio
    filtra por TLS, pedir robots.txt con otro cliente daría un falso negativo).
    """
    if base in _robots_cache:
        return _robots_cache[base]

    parser = None
    try:
        respuesta = fetch(urljoin(base, "/robots.txt"))
        if respuesta is not None and 200 <= respuesta.status_code < 300:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(respuesta.text.splitlines())
    except Exception:
        parser = None  # sin reglas legibles: no bloqueamos por las dudas
    _robots_cache[base] = parser
    return parser


def permitido(url: str, fetch) -> bool:
    parser = _robots(_base(url), fetch)
    if parser is None:
        return True
    return parser.can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------

class PoliteSession:
    """Envuelve una sesión (requests o curl_cffi) con robots.txt e IPv4.

    Expone `get` y `headers`, que es todo lo que usan las fuentes y el
    prospector, así que se puede pasar donde antes iba un `requests.Session`.
    """

    def __init__(self, impersonate: bool = True, force_ipv4: bool = False,
                 respetar_robots: bool = True, timeout: int = 30):
        self.force_ipv4 = force_ipv4
        self.respetar_robots = respetar_robots
        self.timeout = timeout
        # curl_cffi no puede forzar IPv4 desde urllib3, así que cuando hace
        # falta IPv4 se usa requests: el problema ahí es de red, no de WAF.
        self.impersonate = bool(impersonate and curl_requests and not force_ipv4)

        if self.impersonate:
            self._session = curl_requests.Session(impersonate=PERFIL_TLS)
        else:
            self._session = requests.Session()
        self._session.headers.update(BROWSER_HEADERS)

    @property
    def headers(self):
        return self._session.headers

    @property
    def transporte(self) -> str:
        return f"curl_cffi/{PERFIL_TLS}" if self.impersonate else "requests"

    def get_crudo(self, url: str, timeout: Optional[int] = None, **kwargs):
        """GET sin chequear robots.txt. Solo para pedir robots.txt mismo."""
        kwargs.setdefault("timeout", timeout or self.timeout)
        kwargs.setdefault("allow_redirects", True)
        _esperar_turno(url)
        if self.force_ipv4:
            with solo_ipv4():
                return self._session.get(url, **kwargs)
        return self._session.get(url, **kwargs)

    def get(self, url: str, timeout: Optional[int] = None, **kwargs):
        if self.respetar_robots and not permitido(url, self._fetch_robots):
            raise RobotsBloqueado(url)
        return self.get_crudo(url, timeout=timeout, **kwargs)

    def _fetch_robots(self, url: str):
        try:
            return self.get_crudo(url, timeout=15)
        except Exception:
            return None


class RobotsBloqueado(Exception):
    """El robots.txt del sitio prohíbe esa ruta para nuestro User-Agent."""

    def __init__(self, url: str):
        super().__init__(f"robots.txt prohibe {url}")
        self.url = url


def http_session(impersonate: bool = True, force_ipv4: bool = False,
                 respetar_robots: bool = True, timeout: int = 30) -> PoliteSession:
    return PoliteSession(impersonate=impersonate, force_ipv4=force_ipv4,
                         respetar_robots=respetar_robots, timeout=timeout)
