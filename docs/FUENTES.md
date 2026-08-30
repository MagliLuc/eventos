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
| 3 | **CKAN / datos abiertos** | Tablas oficiales — ojo: suelen ser **históricas** | Baja, pero puede no ser agenda | ✅ `BaDataSource` |
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
- **BA Data (CKAN)** — alcanzable desde CI, pero **sus datasets culturales son
  archivo histórico** (ver más abajo). Aporta cero eventos vigentes.
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

### Prospección del 2026-08-30 desde el runner

Quince sitios sondeados contra ocho mecanismos. Resultado crudo:

| Sitio | Resultado |
|---|---|
| **Teatro Colón** | ✅ RSS, 10 entradas → activo |
| **Usina del Arte** | ✅ Atom, 10 entradas → activo |
| Palacio Libertad · MNBA · Complejo Teatral · Cultura Nación | HTTP 403 |
| DisfrutemosBA | ConnectTimeout |
| Baires Secreta | HTTP 202 — challenge de Cloudflare |
| Qué Hacemos · Gratis en BA · Time Out · Alternativa Teatral | 200 sin marcado |
| Centro Cultural Recoleta · Turismo BA | 200 sin marcado |

Lecturas:

- **Los feeds siguen vivos donde uno no los busca.** Teatro Colón y Usina
  publican RSS/Atom y nadie lo miraba: se les estaba raspando el HTML.
- **"200 sin marcado" es el caso mayoritario.** Ni ICS, ni The Events Calendar,
  ni JSON-LD, ni feed, ni `wp-json`. Para esos sitios no hay atajo: o
  selectores CSS, o nada.
- **HTTP 202 en Baires Secreta** es la respuesta típica de un challenge de
  Cloudflare. No se resuelve con cabeceras; haría falta un navegador, que es
  justo lo que este proyecto evita.
- **Los cuatro 403 se repiten** desde el mismo rango de IPs, así que quedan
  consistentes con la hipótesis del bloqueo por IP pero sin probarla: haría
  falta sondear desde otra red.

### Resultado de activarlas (corrida 22:09)

La advertencia se cumplió:

```
[Usina del Arte]  10 notas sin schema.org/Event  ->  0 eventos
[Teatro Colón]    10 notas sin schema.org/Event  ->  0 eventos
```

Los feeds existen y traen diez entradas cada uno, pero **las fichas enlazadas
no marcan `schema.org/Event`**. Sin ese marcado no hay fecha ni sede del
evento, solo la fecha de publicación de la nota — y datear un evento con la
fecha en que se publicó el artículo es exactamente el error que generó siete
copias del mismo evento. Se quedan como activas porque no cuestan nada y
cualquier día pueden empezar a marcar; el log dice si aportan.

**Conclusión sobre RSS en este dominio**: sirve para descubrir URLs, no para
obtener eventos. Salvo que el sitio marque JSON-LD en las fichas, un feed no
alcanza.

### BA Data: no es una agenda (corrección)

```
'teatro-colon-programacion-actual':   18 filas -> 0 en ventana
'eventos-direccion-general-musica':   82 filas -> 0 en ventana
'teatro-colon-visitas-guiadas':     9392 filas -> 0 en ventana
'ba-diversa':                         46 filas -> 0 en ventana
```

El diagnóstico de columnas respondió, y la respuesta desmiente la hipótesis
que se venía sosteniendo. **La detección de fecha funcionaba perfecto**; el
dato es viejo:

```
eventos-direccion-general-musica  ['evento','fecha_desde','barrio','comuna'...]  → 2017-01-07
teatro-colon-visitas-guiadas      ['PERIODO','FECHA','TIPO_VISITAS','VISITAS']   → 2016-01-01
ba-diversa                        [...'fecha_inicio','asistentes_cantidad'...]   → 2015-06-16
bafici                            ['id_filmcolor','name_es','name_en',...]       → sin fecha
```

Las columnas delatan qué son en realidad: `VISITAS` y `asistentes_cantidad`
son **estadísticas de asistencia**, e `id_filmcolor` es una **tabla de códigos
de color de película**. Nada de eso es una agenda.

> **Corrección.** Durante buena parte del trabajo se trató a BA Data como "la
> fuente más prometedora, la única con compromiso institucional de
> actualización". Es falso: **BA Data es un portal de transparencia y
> estadística, no un feed de agenda cultural**. Los datasets con nombre de
> evento son archivos históricos y reportes posteriores. No sirve para saber
> qué pasa mañana.

Se dejan solo `actividades-culturales` y `teatro-colon-programacion-actual`,
los únicos dos que podrían traer programación vigente, y se agrega un aviso
automático: cuando un dataset no produce eventos se reporta **la fecha más
nueva que contiene**, que distingue de un vistazo las dos causas posibles:

- `ninguna fila tiene fecha parseable` → falta un alias de columna.
- `fecha más nueva: 2017-03-02 -> ARCHIVO` → el dataset es histórico.

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
