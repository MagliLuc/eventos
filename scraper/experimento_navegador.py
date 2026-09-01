#!/usr/bin/env python3
"""Experimento acotado: ¿un navegador real pasa el desafío de Cloudflare?

Contexto. Los cuatro `.gob.ar` de la agenda devuelven `Cf-Mitigated: challenge`
en **todas** sus rutas — la página, el sitemap, el feed, wp-json, el .ics. Ya se
descartó con evidencia que sea bloqueo por IP o fingerprinting TLS, y se probó
que no hay ninguna ruta que el CDN sirva cacheada. Lo único que queda es
ejecutar el JavaScript del desafío, que es justo lo que hace un navegador.

Esto NO se integra al pipeline. Corre una vez, contra un solo sitio, e imprime
qué pasó. El criterio de cierre está decidido de antemano:

  * Si pasa  -> recién ahí se escribe la integración (una cookie por dominio,
                y el resto de la corrida sigue con `requests`).
  * Si NO pasa -> se cierra el tema. No se escala a plugins de sigilo, huellas
                falsas ni resolvedores de captcha: es una carrera contra un
                antibot que este proyecto no puede sostener, y además iría
                contra la señal explícita del sitio.

Y hay que decirlo antes de correrlo: **lo más probable es que no pase**.
Cloudflare detecta un Playwright sin disfraz (`navigator.webdriver`, artefactos
de CDP), y ese es exactamente el caso que su Managed Challenge ataja.

Uso:
    python scraper/experimento_navegador.py [url]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eventos.http import BROWSER_HEADERS, USER_AGENT  # noqa: E402

# MNBA: museo grande, con muestras genuinamente gratuitas. Es el que más
# pagaría si entra, y su robots.txt permite /agenda/.
OBJETIVO = "https://www.bellasartes.gob.ar/agenda/"

MARCAS_DE_DESAFIO = (
    "cdn-cgi/challenge-platform", "Just a moment", "Un momento",
    "Verificando que usted es un ser humano", "cf-browser-verification",
)


def url_pedida(argv: list[str]) -> str:
    """URL del primer argumento no vacío, o el objetivo por defecto.

    El "no vacío" importa: cuando el workflow se dispara por push no existe
    `inputs.url`, así que el paso pasa una cadena vacía como argumento.
    """
    for arg in argv:
        if arg.strip():
            return arg.strip()
    return OBJETIVO


def main() -> int:
    url = url_pedida(sys.argv[1:])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright no está instalado; el experimento no puede correr.")
        return 0  # no rompe nada: es un experimento, no una dependencia

    print(f"Abriendo {url} con Chromium…\n")
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={"From": BROWSER_HEADERS["From"],
                                "Accept-Language": BROWSER_HEADERS["Accept-Language"]},
            locale="es-AR",
        )
        pagina = contexto.new_page()
        try:
            respuesta = pagina.goto(url, wait_until="domcontentloaded", timeout=60_000)
            estado = respuesta.status if respuesta else None
            # El desafío se resuelve solo, pero tarda. Se le da tiempo.
            pagina.wait_for_timeout(12_000)

            titulo = pagina.title()
            cuerpo = pagina.inner_text("body")[:400]
            cookies = {c["name"] for c in contexto.cookies()}
        except Exception as exc:
            # Un error de red no es "no pasó el desafío": son cosas distintas y
            # confundirlas daría por cerrado el tema sin haberlo respondido.
            print(f"El navegador no llegó a cargar la página: "
                  f"{type(exc).__name__}: {exc}")
            print("Eso NO responde la pregunta del experimento; hay que "
                  "repetirlo.")
            return 1
        finally:
            navegador.close()

    desafiada = any(m.lower() in (titulo + cuerpo).lower()
                    for m in MARCAS_DE_DESAFIO)

    print(f"  HTTP           : {estado}")
    print(f"  <title>        : {titulo!r}")
    print(f"  cf_clearance   : {'SÍ' if 'cf_clearance' in cookies else 'no'}")
    print(f"  cookies        : {sorted(cookies)[:8]}")
    print(f"  cuerpo (400c)  : {cuerpo!r}\n")

    if desafiada or not titulo:
        print("RESULTADO: NO PASÓ. Sigue viéndose la página de desafío.")
        print("Según lo acordado, acá se cierra: no se escala a plugins de")
        print("sigilo ni a resolvedores de captcha. Documentar en FUENTES.md.")
    else:
        print("RESULTADO: PASÓ. Se ve la página real.")
        print("Recién ahora tiene sentido integrarlo: obtener la cookie una vez")
        print("por dominio y seguir la corrida con requests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
