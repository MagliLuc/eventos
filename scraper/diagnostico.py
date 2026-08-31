#!/usr/bin/env python3
"""Junta evidencia de cada fuente y la deja escrita en el repo.

Por qué existe, y por qué escribe archivos en vez de imprimir: desde donde se
mantiene este scraper **no hay salida a internet hacia estos sitios** (el proxy
rechaza el CONNECT), y quien lo pidió tampoco puede probar nada local. El único
punto de la cadena con red real es el runner de GitHub Actions. Entonces el
runner mira, y deja lo que vio commiteado en `scraper/diagnostico/` para que se
puedan escribir selectores contra el marcado de verdad en vez de adivinarlo.

Lo que responde, por sitio:

  * ¿robots.txt nos deja? (y si no, se acabó la discusión para esa ruta)
  * ¿el 403 es por IP o por forma del pedido? Si robots.txt da 200 desde la
    misma IP y el mismo cliente, y la agenda da 403, no es la IP.
  * ¿es fingerprinting TLS? Si `curl_cffi` con el perfil de Chrome pasa donde
    `requests` falla, sí: el WAF decidió mirando el ClientHello, antes de leer
    una sola cabecera. Es la hipótesis que explica por qué mandar diez
    cabeceras de navegador no movió nada.
  * ¿el timeout es IPv6 sin ruta? Se repite el pedido forzando IPv4.
  * ¿hay un mecanismo mejor que los selectores? Feeds declarados en el <head>,
    sitemap, y —esto es lo que más suele destrabar— JSON-LD en la *ficha* del
    evento aunque el listado no lo tenga.

Uso:
    python scraper/diagnostico.py              # todas las fuentes del registro
    python scraper/diagnostico.py https://x.ar # una suelta
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning  # noqa: E402

# Sondeamos a ciegas: sitemaps y feeds llegan al mismo parser que el HTML.
# El aviso es correcto pero acá es ruido que tapa el resultado en el log.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from eventos.http import (  # noqa: E402
    RobotsBloqueado,
    hay_tls_de_navegador,
    http_session,
    permitido,
)
from eventos.models import slugify  # noqa: E402
from eventos.sources.base import extract_jsonld_events  # noqa: E402

SALIDA = Path(__file__).resolve().parent / "diagnostico"

# Cabeceras que delatan quién decidió el bloqueo y con qué producto.
CABECERAS_INTERES = (
    "server", "via", "cf-ray", "cf-cache-status", "cf-mitigated",
    "x-akamai-transformed", "x-sucuri-id", "x-iinfo", "x-cache",
    "content-type", "x-powered-by", "link", "retry-after",
)

RUTAS_SITEMAP = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")
PALABRAS_EVENTO = ("evento", "agenda", "actividad", "cartelera", "espectaculo",
                   "muestra", "exposicion", "programacion", "funcion")

TOPE_HTML = 200_000  # bytes por sitio: alcanza de sobra para leer el maquetado


# ---------------------------------------------------------------------------
# Registro de una respuesta
# ---------------------------------------------------------------------------

def _registrar(sesion, url: str, timeout: int = 30) -> dict:
    """Pide la URL y anota todo lo que sirva para explicar el resultado."""
    try:
        r = sesion.get(url, timeout=timeout)
    except RobotsBloqueado:
        return {"url": url, "resultado": "robots.txt lo prohibe"}
    except Exception as exc:
        return {"url": url, "resultado": "error",
                "error": f"{type(exc).__name__}: {exc}"}

    cabeceras = {k: v for k, v in r.headers.items()
                 if k.lower() in CABECERAS_INTERES}
    cookies = sorted({c.split("=")[0] for c in r.headers.get("set-cookie", "").split(",")
                      if "=" in c})
    return {
        "url": url,
        "resultado": "ok" if r.status_code == 200 else f"HTTP {r.status_code}",
        "status": r.status_code,
        "bytes": len(r.content or b""),
        "cabeceras": cabeceras,
        "cookies": cookies[:6],
        "final": getattr(r, "url", url),
    }


def _texto(sesion, url: str, timeout: int = 30) -> str:
    try:
        r = sesion.get(url, timeout=timeout)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Sondas
# ---------------------------------------------------------------------------

def _base(url: str) -> str:
    partes = urlparse(url)
    return f"{partes.scheme}://{partes.netloc}"


def feeds_declarados(sopa: BeautifulSoup, base: str) -> list[str]:
    """Los feeds que el propio sitio anuncia en el <head>.

    Adivinar /feed, /rss y compañía falla cuando el feed vive en otra ruta.
    El <link rel="alternate"> lo dice sin adivinar.
    """
    urls = []
    for nodo in sopa.select('link[rel="alternate"]'):
        tipo = (nodo.get("type") or "").lower()
        if "xml" in tipo or "json" in tipo:
            href = nodo.get("href")
            if href:
                urls.append(urljoin(base, href))
    return sorted(set(urls))


def urls_de_sitemap(sesion, base: str) -> tuple[str, list[str]]:
    """Primer sitemap que responda y las URLs que parecen ficha de evento."""
    for ruta in RUTAS_SITEMAP:
        crudo = _texto(sesion, urljoin(base, ruta), timeout=25)
        if "<urlset" not in crudo and "<sitemapindex" not in crudo:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", crudo)
        interesantes = [u for u in locs
                        if any(p in u.lower() for p in PALABRAS_EVENTO)]
        return urljoin(base, ruta), (interesantes or locs)[:15]
    return "", []


def links_de_detalle(sopa: BeautifulSoup, base: str, listado: str) -> list[str]:
    """Links de la página que parecen ir a la ficha de una actividad."""
    candidatos: list[str] = []
    for a in sopa.find_all("a", href=True):
        destino = urljoin(listado, a["href"])
        if not destino.startswith(base) or destino.rstrip("/") == listado.rstrip("/"):
            continue
        ruta = urlparse(destino).path.lower()
        if any(p in ruta for p in PALABRAS_EVENTO) and len(ruta.strip("/").split("/")) >= 2:
            candidatos.append(destino.split("#")[0])
    vistos: list[str] = []
    for u in candidatos:
        if u not in vistos:
            vistos.append(u)
    return vistos[:5]


def jsonld_en_fichas(sesion, urls: list[str]) -> list[dict]:
    """La pregunta que más destraba: ¿la ficha trae schema.org/Event?

    Es muy común que el listado se arme por JavaScript y no tenga marcado,
    pero que cada ficha sí lo emita. Si pasa, no hacen falta selectores: se
    entra por sitemap o por los links del listado y se lee JSON-LD.
    """
    hallazgos = []
    for url in urls:
        crudo = _texto(sesion, url, timeout=25)
        if not crudo:
            hallazgos.append({"url": url, "eventos": 0, "nota": "no responde"})
            continue
        nodos = extract_jsonld_events(BeautifulSoup(crudo, "lxml"))
        hallazgos.append({
            "url": url,
            "eventos": len(nodos),
            "muestra": [{"name": n.get("name"), "startDate": n.get("startDate"),
                         "offers": n.get("offers")} for n in nodos[:2]],
        })
    return hallazgos


def wayback(sesion, url: str) -> dict:
    """Último recurso: si el sitio nos cierra la puerta, ¿hay copia archivada?

    Sirve para muestras y programación estable, no para 'qué hay hoy'.
    """
    api = "https://archive.org/wayback/available?url=" + url
    crudo = _texto(sesion, api, timeout=25)
    try:
        datos = json.loads(crudo).get("archived_snapshots", {}).get("closest", {})
    except Exception:
        return {}
    return {"disponible": bool(datos.get("available")),
            "timestamp": datos.get("timestamp"), "url": datos.get("url")}


# ---------------------------------------------------------------------------
# Un sitio
# ---------------------------------------------------------------------------

def revisar(entrada: dict) -> dict:
    url = entrada["url"]
    nombre = entrada.get("name") or url
    base = _base(url)
    print(f"\n=== {nombre} — {url}")

    # Sin robots: queremos ver el 403 crudo del sitio, no frenarnos solos.
    plano = http_session(impersonate=False, respetar_robots=False)
    chrome = http_session(impersonate=True, respetar_robots=False)
    ipv4 = http_session(impersonate=False, force_ipv4=True,
                        respetar_robots=False, timeout=60)

    informe: dict = {
        "name": nombre,
        "url": url,
        "status_registro": entrada.get("status"),
        "tls_navegador_disponible": hay_tls_de_navegador(),
    }

    informe["robots"] = _registrar(plano, urljoin(base, "/robots.txt"), timeout=20)
    informe["robots"]["permite_la_ruta"] = permitido(
        url, lambda u: plano.get_crudo(u, timeout=20))

    informe["requests"] = _registrar(plano, url)
    informe["curl_cffi_chrome"] = _registrar(chrome, url)
    informe["ipv4_forzado"] = _registrar(ipv4, url, timeout=60)

    # Un 404 en la ruta configurada no dice si el dominio sirve: la URL puede
    # estar simplemente mal. Distinguirlo evita descartar un sitio bueno.
    if informe["requests"].get("status") == 404 and base != url.rstrip("/"):
        informe["raiz_responde"] = _registrar(plano, base).get("status")

    for etiqueta in ("robots", "requests", "curl_cffi_chrome", "ipv4_forzado"):
        print(f"  {etiqueta:<18} {informe[etiqueta].get('resultado')}")

    # --- veredicto, que es lo que se lee de un vistazo en el log ---
    informe["veredicto"] = _veredicto(informe)
    print(f"  -> {informe['veredicto']}")

    # --- si alguna vía trajo HTML, se explota ---
    exitosa = plano
    crudo = ""
    for sesion in (chrome, plano, ipv4):
        crudo = _texto(sesion, url, timeout=45)
        if crudo:
            exitosa = sesion
            informe["transporte_que_funciono"] = sesion.transporte + (
                " (IPv4 forzado)" if sesion.force_ipv4 else "")
            break

    if not crudo:
        informe["wayback"] = wayback(plano, url)
        print(f"  wayback: {informe['wayback'] or 'sin copia'}")
        return informe

    sopa = BeautifulSoup(crudo, "lxml")
    informe["titulo_pagina"] = (sopa.title.get_text(strip=True)
                                if sopa.title else None)
    informe["feeds_declarados"] = feeds_declarados(sopa, base)
    informe["sitemap"], informe["urls_sitemap"] = urls_de_sitemap(exitosa, base)
    informe["jsonld_en_listado"] = len(extract_jsonld_events(sopa))

    fichas = links_de_detalle(sopa, base, url) or informe["urls_sitemap"][:3]
    informe["fichas_probadas"] = jsonld_en_fichas(exitosa, fichas[:3])
    con_evento = sum(f.get("eventos", 0) for f in informe["fichas_probadas"])
    informe["jsonld_en_fichas"] = con_evento

    print(f"  feeds declarados : {informe['feeds_declarados'] or 'ninguno'}")
    print(f"  sitemap          : {informe['sitemap'] or 'ninguno'}"
          f" ({len(informe['urls_sitemap'])} urls de evento)")
    print(f"  JSON-LD listado  : {informe['jsonld_en_listado']}")
    print(f"  JSON-LD fichas   : {con_evento} en {len(informe['fichas_probadas'])} fichas")

    _guardar_html(nombre, sopa)
    return informe


def _veredicto(informe: dict) -> str:
    """Traduce los cuatro intentos a la causa concreta del problema."""
    robots = informe["robots"].get("status")
    plano = informe["requests"].get("status")
    chrome = informe["curl_cffi_chrome"].get("status")
    ipv4 = informe["ipv4_forzado"].get("status")

    if not informe["robots"].get("permite_la_ruta", True):
        return "robots.txt nos prohibe esta ruta: no se scrapea, punto."
    if plano == 200:
        return "responde bien con requests; el problema no es el transporte"
    if chrome == 200 and plano != 200:
        return ("FINGERPRINTING TLS confirmado: el perfil de Chrome pasa donde "
                "requests no. Usar curl_cffi en esta fuente.")
    if ipv4 == 200 and plano != 200:
        return ("era IPv6 sin ruta: forzando IPv4 responde. Marcar "
                "force_ipv4 en sources.json.")
    if 429 in (plano, chrome, ipv4):
        # Un 429 no dice nada del sitio: dice que pedimos demasiado rapido.
        return ("HTTP 429: es ritmo, no bloqueo. El sitio responde; hay que "
                "espaciar los pedidos y volver a probar.")
    if plano == 404:
        raiz = informe.get("raiz_responde")
        if raiz == 200:
            return ("404: la URL esta mal, pero el dominio responde. Sondear la "
                    "raiz con discover.py para encontrar la agenda.")
        return "404: la URL configurada no existe. Hay que corregirla."
    if plano is None and chrome is None and ipv4 is None:
        return "no responde por ninguna via: caida, DNS o bloqueo de red"
    if robots == 200 and plano in (403, 202):
        return (f"HTTP {plano} en la agenda pero robots.txt da 200 desde la misma "
                f"IP y el mismo cliente: NO es bloqueo por IP ni fingerprinting "
                f"TLS (el perfil de Chrome da lo mismo). Queda un WAF que exige "
                f"cookie de challenge, o filtro por pais.")
    return f"sin via de acceso (requests {plano}, chrome {chrome}, ipv4 {ipv4})"


def _guardar_html(nombre: str, sopa: BeautifulSoup) -> None:
    """Deja el HTML sin scripts para poder escribir selectores mirandolo."""
    for basura in sopa.find_all(["script", "style", "noscript", "svg"]):
        basura.decompose()
    destino = SALIDA / f"{slugify(nombre)}.html"
    destino.write_text(str(sopa)[:TOPE_HTML], encoding="utf-8")
    print(f"  HTML guardado en {destino.relative_to(SALIDA.parent.parent)}")


# ---------------------------------------------------------------------------

def main() -> int:
    from eventos.registry import REGISTRO

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        entradas = [{"name": u, "url": u} for u in args]
    else:
        datos = json.loads(REGISTRO.read_text(encoding="utf-8"))
        entradas = [e for e in datos.get("sources", [])
                    if e.get("url") and e.get("kind") != "ckan"]

    SALIDA.mkdir(parents=True, exist_ok=True)
    if not hay_tls_de_navegador():
        print("AVISO: curl_cffi no esta instalado; no se puede probar la "
              "hipotesis de fingerprinting TLS.")

    informes = []
    for entrada in entradas:
        try:
            informes.append(revisar(entrada))
        except Exception as exc:  # un sitio roto no corta el diagnostico
            print(f"  ERROR irrecuperable: {type(exc).__name__}: {exc}")
            informes.append({"name": entrada.get("name"), "url": entrada["url"],
                             "error": f"{type(exc).__name__}: {exc}"})

    (SALIDA / "informe.json").write_text(
        json.dumps(informes, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("RESUMEN\n")
    for informe in informes:
        print(f"  {informe.get('name', '?'):<38} "
              f"{informe.get('veredicto') or informe.get('error', '?')}")
    print(f"\nDetalle en scraper/diagnostico/informe.json y los .html de al lado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
