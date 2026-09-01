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
| 7 | **JSON-LD en la ficha** | El evento, aunque el listado no lo marque | Media-baja | ✅ `FichasSource` |
| 8 | **WordPress `/wp/v2/posts`** | Artículos | Media | 🔍 lo detecta `discover.py` |
| 9 | **Fecha escrita en la prosa** | Fecha y hora, si están literales | Media-alta | ✅ `eventos/fechas.py` |
| 10 | **Selectores CSS** | Lo que se logre sacar | **Alta** — muere con cada rediseño | ✅ último recurso |
| 11 | **Navegador headless** | Cualquier cosa | Alta + costo de CI | ❌ evitado |

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

**Antes de escribir selectores, mirar la ficha.** El mecanismo 7 es el que más
fuentes destrabó: es habitual que el *listado* se arme por JavaScript y no
tenga nada que leer, mientras la ficha de cada actividad emite
`schema.org/Event` porque el CMS lo genera solo. `FichasSource` usa el listado
únicamente como índice. Es preferible a los selectores porque no depende del
maquetado del listado, que es justo lo que más cambia.

**La prosa es el último recurso antes de rendirse, y tiene reglas.** Cuando la
ficha no marca nada, se lee el texto — pero la fecha tiene que estar
**escrita**. Nada de resolver «este finde» contra el día de la corrida: eso es
lo que una vez produjo siete copias del mismo evento. Por eso `fechas.py` usa
expresiones regulares y **no** `dateparser`, cuya gracia es precisamente
inferir fechas relativas a hoy. Además, en prosa se exige que el texto diga que
es gratis: `is_free` acepta por defecto lo que no menciona precio, y eso sirve
para JSON-LD (donde existe el campo `offers`) pero no para una nota
periodística, donde el silencio no significa gratis.

---

## 2. Cómo se decide, y por qué CI es el único que puede mirar

Desde donde se mantiene este scraper **no hay salida a internet hacia los
sitios objetivo**: el proxy rechaza el CONNECT a `palaciolibertad.gob.ar`,
`bellasartes.gob.ar` y compañía, y la herramienta de fetch devuelve
`EGRESS_BLOCKED`. Quien lo pidió tampoco puede probar nada en su máquina. El
único punto de la cadena con red real es el runner de Actions.

De ahí sale la regla de trabajo de este archivo: **ningún estado de
`sources.json` se escribe por deducción**. Lo decide una corrida.

`scraper/diagnostico.py` (workflow «Diagnóstico de fuentes») pide cada sitio
por cuatro caminos y **commitea lo que vio** en `scraper/diagnostico/` —
archivos, no un artifact `.zip`, porque un artifact no se puede leer desde
acá y el HTML real es lo que permite escribir selectores sin adivinarlos.

Lo que cada combinación significa:

| robots.txt | `requests` | `curl_cffi` (TLS de Chrome) | IPv4 forzado | Conclusión |
|---|---|---|---|---|
| 200 | 200 | — | — | El transporte no es el problema |
| 200 | 403 | **200** | — | **Fingerprinting TLS**: activar `curl_cffi` |
| 200 | timeout | timeout | **200** | AAAA sin ruta: marcar `force_ipv4` |
| 200 | 403 | 403 | 403 | Ni TLS ni IPv6. **Mirar las cabeceras**: ahí está el mecanismo real |
| — | prohibido por robots | — | — | No se scrapea, punto |

**La conclusión no está en el código de estado: está en las cabeceras.** Dos
que deciden todo:

- `Cf-Mitigated: challenge` — Cloudflare sirvió una **página de desafío** en
  lugar de la respuesta. Se resuelve ejecutando el JavaScript del desafío y
  quedándose con la cookie `cf_clearance`; no se resuelve cambiando de IP ni de
  país.
- `cf-cache-status: HIT` — la respuesta salió de la caché del borde y **nunca
  llegó al origen**.

### Una corrección, porque el error es instructivo

Acá se afirmó: *«si robots.txt responde 200 desde la misma IP y con el mismo
cliente, y la agenda no, no es bloqueo por IP»*. **Para el Complejo Teatral eso
es falso**: su robots.txt volvió con `cf-cache-status: HIT`, o sea servido por
la caché sin tocar el origen ni el desafío. No probaba nada sobre la IP.

Lo que sí quedó probado, con las cabeceras a la vista: los cuatro `.gob.ar` y
Baires Secreta devuelven un **desafío del CDN** (Cloudflare en los cuatro,
CloudFront en Baires Secreta). Y la hipótesis del fingerprinting TLS quedó
descartada aparte: `curl_cffi` con perfil de Chrome recibe el mismo 403 que
`requests` — y en Gratis en Buenos Aires es directamente peor, porque ahí
`requests` pasa con 200 y el perfil de Chrome recibe 403.

### Por qué un proxy argentino no es la respuesta

Se evaluó, porque parecía lo obvio:

- **VPN gratuita con salida argentina no existe**: ProtonVPN free da 5 países y
  Windscribe free 11; en los dos, Argentina es plan pago.
- **Cloudflare Workers free** (100k pedidos/día, sin tarjeta) no deja elegir
  país de egreso: saldría por EE.UU. igual que el runner.
- **Listas de proxies públicos argentinos**: existen, pero son IPs que caen sin
  aviso, ya vienen marcadas, y meten un intermediario que puede alterar el
  contenido en tránsito. No se justifica para leer una agenda pública.
- Y el punto de fondo: **ninguno ejecuta el JavaScript del desafío**, que es lo
  que el CDN está pidiendo.

Lo que sí queda por probar, y es gratis: que el mismo CDN sirva alguna ruta con
datos desde su caché (`sitemap.xml`, `/feed`, `wp-json`, `.ics`). El
diagnóstico las sondea cuando la agenda viene desafiada.

Dos límites que nos ponemos, y no son decorativos: `robots.txt` manda (si el
sitio nos prohíbe la ruta, no se pide), y seguimos identificados — `From` y el
User-Agent llevan la URL del proyecto, así que quien administre el sitio sabe
quiénes somos y cómo frenarnos. Son páginas públicas y el volumen es un puñado
de pedidos por día.

---

## 3. Estado real de las fuentes

Medido en la corrida en seco del pipeline (workflow «Diagnóstico de fuentes»,
paso *Corrida en seco*), no supuesto. **26 eventos de fuentes en vivo**, contra
0 cuando empezó este trabajo.

### Aportando eventos

| Fuente | Fichas | Eventos | Cómo |
|---|---|---|---|
| **Museo Moderno** | 10 | **14** | prosa de la ficha; 8 de 10 con actividad |
| **Centro Cultural Recoleta** | 27 | **11** | fecha en la tarjeta del listado |
| **Qué Hacemos** | 8 | **1** | `schema.org/Event` en cada ficha |

Qué Hacemos rinde poco en número pero es la de mejor dato: su marcado es
impecable y el filtro descarta bien los shows pagos que su sección «eventos
gratis» también enlaza. Su sitemap tiene 10 URLs más para explorar.

### Activas, todavía sin aportar — con el motivo medido

| Fuente | Qué pasa |
|---|---|
| **Teatro Colón** | 9 fichas, 9 dicen «Comprar entradas». Es el resultado correcto: el Colón vende entradas. Queda activa por las funciones gratuitas que sí hace. |
| **Usina del Arte** | 10 fichas; su listado muestra actividades ya pasadas. Cuando publique la agenda siguiente entra sola. |
| **El Cultural San Martín** | 40 fichas por sitemap, pero el sitemap trae páginas del sitio y no funciones. Falta un `ruta_ficha` sacado de su HTML. |
| **Fundación Proa** | enlaza una sola ficha y su fecha cayó fuera de la ventana. |

### Fuera, con motivo probado

- **BA Data (CKAN)** — su propio `robots.txt` prohíbe `/api/`. No se fuerza: la
  regla vale también cuando incomoda. Da igual para el resultado, porque ya
  estaba probado que sus datasets culturales son archivo (2015-2017) y
  estadística, no agenda.
- **Turismo BA** — su sitemap está podrido: de 21 URLs, 12 dan 404 y el resto
  son notas de 2016-2018. Gastaba 21 pedidos por corrida en nada.
- **Planetario** — sus espectáculos cuelgan de la raíz sin prefijo común
  (`/agujeros-negros-supermasivos`, `/alerta-espacial…`), así que ningún
  `ruta_ficha` los distingue del menú. Y tiene `/tickets`: además son pagos.

### Un dominio secuestrado, y la guarda que salió de ahí

**`elculturalsanmartin.org` está comprometido.** No es un problema de
extracción: el dominio sirve spam de apuestas en turco.

```
<title>Canlı Bahis Siteleri - En Güvenilir Canlı Bahis Sitesi Listesi 2026
75 enlaces a /canli-bahis/   ("apuestas en vivo")
imágenes en wp-content/uploads/2022/12/canli-bahis-siteleri-….jpg
```

Un WordPress hackeado desde diciembre de 2022. Estaba **`activo`** en el
registro y el scraper lo consultaba en cada corrida. No llegó a publicar nada
sólo porque `is_explicitly_free()` exige la palabra «gratis» en castellano y el
spam no la traía: **nos salvó la suerte, no el diseño**. Si un dominio
secuestrado publicara la palabra correcta, sus URLs entrarían a la app.

De ahí sale la guarda de `idioma_ajeno()` en `sources/feeds.py`: si el listado
declara un `<html lang>` que no es castellano, la fuente se descarta entera con
un aviso ruidoso. Ataca la clase entera de problema —dominio vencido,
secuestrado o redirigido— y no este caso puntual. Sólo rechaza cuando el
atributo existe y no es `es*`; los sitios que no lo declaran siguen igual.

El `<title>` turco estaba a la vista desde la primera corrida del diagnóstico y
no se miró. Por eso ahora el informe registra `lang` y `title` de cada sitio.

**La sala existe**; lo tomado es el `.org`. Su dominio real quedó como
candidato a sondear, sin inventarlo.

### Sin solución dentro de la restricción de costo cero

Los cuatro `.gob.ar` (`bellasartes`, `complejoteatral`, `cultura`,
`palaciolibertad`) y Baires Secreta. La sección 2 explica qué quedó descartado
y qué queda: un WAF con cookie de challenge o un filtro por país. Ninguno se
resuelve desde un runner en EE.UU. sin pagar un proxy, así que **se documentan
en vez de seguir intentando**. `disfrutemosba` y Konex directamente no
responden por ninguna vía.

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

## 4. Redes sociales

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

## 5. Cómo sumar una fuente

1. Agregarla a `sources.json` con `"status": "candidato"`.
2. Correr `python scraper/discover.py` **desde una red con acceso real**.
3. Pegar en `sources.json` el JSON que imprime al final.
4. Commitear. `update-events.yml` corre solo al detectar cambios en `scraper/`.

No hace falta escribir Python salvo que el sitio use un mecanismo que todavía
no está en la tabla de arriba.

---

## 6. Principios que salieron de equivocarnos

- **No inventar datos.** Sin fecha legible, el evento se descarta. Sin sede
  ubicable, también: a un evento sin lugar no se puede ir.
- **Fallar ruidoso.** Una fuente que devuelve cero sin loguear por qué costó
  dos corridas de diagnóstico. Todo camino sin salida imprime el motivo.
- **Verificar antes de escribir.** Cada suposición sobre un sitio que no se
  pudo probar —el id de un dataset, un dominio, el formato de un recurso—
  terminó siendo incorrecta. De ahí que exista `discover.py`.
