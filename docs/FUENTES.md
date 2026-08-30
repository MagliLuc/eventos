# Fuentes de eventos: panorama, mecanismos y estado

Documento de trabajo. Registra **qué se probó, qué resultó y por qué**, para no
volver a suponer lo mismo dos veces. El registro ejecutable es
[`scraper/sources.json`](../scraper/sources.json); esto explica el criterio.

---

## 1. Mecanismos de extracción, de mejor a peor

El mecanismo importa más que el sitio: define cuánta interpretación hace falta
y cada capa de interpretación es una fuente de error.

| # | Mecanismo | Qué da | Fragilidad | Implementado |
|---|---|---|---|---|
| 1 | **iCalendar (.ics)** | Fecha, hora, lugar ya normalizados | Muy baja — formato RFC 5545 | ✅ `IcsSource` |
| 2 | **The Events Calendar (WP)** | JSON con `start_date`, `venue`, **`cost`** | Muy baja — API versionada | ✅ `TribeEventsSource` |
| 3 | **CKAN / datos abiertos** | Tablas oficiales (CSV o datastore) | Baja — pero los ids cambian | ✅ `BaDataSource` |
| 4 | **JSON-LD schema.org/Event** | Evento estructurado en el HTML | Baja — sobrevive rediseños | ✅ `HtmlAgendaSource` |
| 5 | **API interna de la SPA** | Lo mismo que ve la web | Media — no versionada | 🔍 lo detecta `discover.py` |
| 6 | **RSS / Atom** | Artículos, **no eventos** | Media | ✅ `RssSource` (+ JSON-LD por ficha) |
| 7 | **WordPress `/wp/v2/posts`** | Artículos | Media | 🔍 lo detecta `discover.py` |
| 8 | **Selectores CSS** | Lo que se logre sacar | **Alta** — muere con cada rediseño | ✅ último recurso |
| 9 | **Navegador headless** | Cualquier cosa | Alta + costo de CI | ❌ evitado |

Dos aclaraciones que evitan expectativas falsas:

**RSS no es una fuente de eventos.** Un ítem trae título, link y fecha *de
publicación*. No trae cuándo ni dónde es el evento. Por eso `RssSource` usa el
feed solo para descubrir fichas y después busca JSON-LD dentro de cada una. Si
la nota no marca eventos, se descarta: **es preferible publicar menos y
correcto antes que inventar fechas**. Ya nos pasó una vez y generó siete copias
del mismo evento.

**El navegador headless casi siempre es evitable.** Si el contenido se renderiza
con JS, el dato viene de una llamada `fetch` — y esa llamada devuelve JSON
limpio. Buscar ese endpoint (mecanismo 5) cuesta cinco minutos y ahorra 30
segundos y cientos de MB por corrida.

---

## 2. Estado real de las fuentes

Verificado en corridas de GitHub Actions del 2026-08-30, no supuesto.

### Funcionando
- **BA Data (CKAN)** — alcanzable desde CI. 454 datasets. Devuelve 502
  intermitente, por eso el GET reintenta ante 5xx.
- **Usina del Arte**, **Centro Cultural Recoleta**, **Turismo BA** — responden
  200 pero los selectores no extraen fecha. Necesitan `discover.py`.

### Bloqueadas: 403 desde GitHub Actions
`palaciolibertad.gob.ar`, `bellasartes.gob.ar`, `complejoteatral.gob.ar`,
`cultura.gob.ar` devuelven **403 en los tres intentos, también con un set
completo de cabeceras de navegador**. Eso descarta el filtrado por User-Agent.

El dato que orienta: `data.buenosaires.gob.ar` **sí** responde desde el mismo
runner. Que caigan los cuatro `www.*` y no el portal de datos apunta a
**bloqueo por IP de datacenter** — los runners de GitHub corren en rangos de
Azure en EE.UU.

> **Cómo confirmarlo**: correr `python scraper/discover.py` desde una red
> argentina. Si esos sitios responden 200 ahí y 403 en CI, es la IP. Ningún
> cambio de código lo arregla; hay que mover *dónde* corre el scraper.

### Sin probar (candidatas)
Ver `sources.json`. Las más prometedoras por calce temático:
**Gratis en Buenos Aires** (agenda diaria, 100% gratuitos), **Qué Hacemos**
(sección dedicada a eventos gratis) y **DisfrutemosBA** (agenda oficial del
GCBA, SPA — lo valioso es su endpoint interno).

---

## 3. Redes sociales

Investigado. El resumen es que **casi todo está cerrado**, y conviene saberlo
antes de invertir tiempo.

| Plataforma | Estado | Sirve |
|---|---|---|
| **Instagram** | No hay búsqueda pública por hashtag desde 2020. La Basic Display API se apagó en diciembre de 2024. La Graph API solo lee cuentas propias de empresa | ❌ |
| **Facebook Events** | API cerrada hace años | ❌ |
| **Meetup** | GraphQL con OAuth atado a Meetup Pro (pago) | ❌ |
| **X / Twitter** | API paga | ❌ |
| **Telegram** | **Bot API gratuita y documentada.** Un bot en un canal público de agenda recibe los mensajes | ⚠️ viable |
| **Mastodon** | API abierta, sin key, `/api/v1/timelines/tag/:hashtag` | ⚠️ viable, poco volumen local |
| **Reddit** | API gratuita con OAuth; r/BuenosAires | ⚠️ bajo volumen de agenda |

Sobre raspar Instagram igual: sus términos lo prohíben explícitamente
("no podés recolectar datos por medios automatizados"). Aunque en EE.UU. varios
fallos sostienen que raspar datos públicos no viola la CFAA, en el caso
*Meta v. Bright Data* prosperaron los reclamos por incumplimiento contractual,
y en Europa las agencias de protección de datos vienen multando fuerte el
raspado de datos personales (Clearview: 30,5 M€ en Países Bajos, 20 M€ en
Italia). Para un proyecto de agenda cultural, el riesgo no compensa: **los
mismos eventos están en las webs oficiales**, que es de donde conviene sacarlos.

**Lo único que recomiendo de acá**: un bot de Telegram suscrito a canales de
agenda porteña. Es gratis, está permitido y no requiere raspar nada.

---

## 4. Cómo sumar una fuente

1. Agregarla a `sources.json` con `"status": "candidato"`.
2. Correr `python scraper/discover.py` **desde una red con acceso real**.
3. Pegar en `sources.json` el JSON que imprime al final.
4. Commitear. `update-events.yml` corre solo al detectar cambios en `scraper/`.

No hace falta escribir Python salvo que el sitio use un mecanismo que todavía
no está en la tabla de arriba.

---

## 5. Principios que salieron de equivocarnos

- **No inventar datos.** Sin fecha legible, el evento se descarta. Sin sede
  ubicable, también: a un evento sin lugar no se puede ir.
- **Fallar ruidoso.** Una fuente que devuelve cero sin loguear por qué costó
  dos corridas de diagnóstico. Todo camino sin salida imprime el motivo.
- **Verificar antes de escribir.** Cada suposición sobre un sitio que no se
  pudo probar —el id de un dataset, un dominio, el formato de un recurso—
  terminó siendo incorrecta. De ahí que exista `discover.py`.
