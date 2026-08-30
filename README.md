# Agenda Gratis BA

App Android para descubrir, filtrar y organizar la agenda de **eventos gratuitos
y culturales de la Ciudad de Buenos Aires**.

### ⬇️ [Descargar el APK](https://github.com/MagliLuc/eventos/releases/latest/download/agenda-gratis-ba.apk)

Android 7.0 (API 24) o superior. El enlace es permanente y siempre sirve el
último build de `main`: cada push a esa rama recompila y republica la release
`latest`. También está el botón en <https://magliluc.github.io/eventos/>.

Todo el stack es open source o de uso gratuito sin límite: **no hay ninguna
pieza que pida tarjeta de crédito, suscripción ni API key.**

---

## 1. Por qué cuesta $0

| Necesidad | Solución habitual (paga) | Lo que usamos | Costo |
|---|---|---|---|
| Backend / API | AWS, Heroku, Supabase, Firebase | `events.json` estático en **GitHub Pages** | $0, ilimitado en repos públicos |
| Automatización | Cron en un VPS | **GitHub Actions** (1 corrida diaria, ~1 min) | $0 en repos públicos |
| Mapas | Google Maps SDK (exige tarjeta y cobra por cuota) | **OpenStreetMap** vía **osmdroid** (Apache 2.0) | $0, sin API key |
| Calendario | SDK de terceros | `Intent(ACTION_INSERT)` al calendario nativo | $0, sin permisos |
| Navegación | SDK de mapas | `Intent` con esquema `geo:` → la app que el usuario ya tiene | $0 |
| Base de datos | Backend gestionado | **Room / SQLite** en el dispositivo | $0 |
| Push / actualizaciones | FCM, OneSignal | **WorkManager** + un GET diario | $0 |

La única cuenta necesaria es una cuenta de GitHub gratuita.

---

## 2. Arquitectura

```
┌──────────────────────── GitHub (gratis) ────────────────────────┐
│                                                                  │
│  scraper/ (Python + BeautifulSoup)                               │
│      │  corre en GitHub Actions, todos los días a las 06:00 ART  │
│      ▼                                                           │
│  docs/events.json  ──publicado por──▶  GitHub Pages (HTTPS+CDN)  │
└──────────────────────────────┬───────────────────────────────────┘
                               │  un solo GET por día
┌──────────────────────────────▼─────────────────── App Android ───┐
│                                                                   │
│  data/remote   Retrofit + kotlinx.serialization  → EventDto       │
│       │                                                           │
│  data/repository  EventRepository (única fuente de verdad)        │
│       │                                                           │
│  data/local    Room: events + favorites  ← CACHÉ OFFLINE          │
│       │                                                           │
│  domain/model  Event, Category, AccessMode, EventFilter           │
│       │                                                           │
│  ui/  Jetpack Compose + ViewModel (MVVM)                          │
│       ├── home/    HomeScreen, EventCard, FilterBar               │
│       ├── map/     OsmMap (osmdroid) + MapScreen                  │
│       └── detail/  EventDetailScreen → Intents nativos            │
└───────────────────────────────────────────────────────────────────┘
```

**Offline-first.** La UI observa siempre Room, nunca la red. `refresh()` solo
empuja datos hacia la base; si la descarga falla, la pantalla ni se entera y
sigue mostrando la última agenda válida. Por eso la app es usable en el subte.

**Filtrado en memoria.** Los ~20-150 eventos de una semana entran holgados en
RAM, así que los filtros (categoría, barrio, franja horaria, modalidad de
ingreso, búsqueda de texto) se aplican sobre la lista ya cacheada: responden
instantáneo mientras se tipea y no tocan ni la red ni SQL.

**DI a mano.** `di/AppContainer` crea la base, el cliente HTTP y el repositorio
`by lazy`. Para un grafo de tres objetos, Hilt agregaría procesamiento de
anotaciones y tiempo de build sin dar nada a cambio.

---

## 3. Esquema del JSON

El contrato entre el bot y la app está en
[`docs/events.schema.json`](docs/events.schema.json) (JSON Schema 2020-12).

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-30T06:00:00-03:00",
  "events": [
    {
      "id": "usina-del-arte-gran-milonga-de-cierre-2026-08-30",
      "title": "Gran Milonga de Cierre del Festival de Tango",
      "description": "Clase magistral y pista abierta…",
      "category": "MUSICA",
      "tags": ["tango", "milonga"],
      "date": "2026-08-30",
      "start_time": "17:00",
      "end_time": "20:30",
      "all_day": false,
      "access_mode": "ORDEN_DE_LLEGADA",
      "reservation_url": null,
      "venue": {
        "id": "usina-del-arte",
        "name": "Usina del Arte",
        "address": "Caffarena 1",
        "neighborhood": "La Boca",
        "commune": 4,
        "lat": -34.6390,
        "lon": -58.3576
      },
      "source_name": "Tango BA",
      "source_url": "https://tangoba.org/…",
      "image_url": null,
      "updated_at": "2026-08-30T06:00:00-03:00"
    }
  ]
}
```

**Categorías:** `MUSICA`, `ARTES_VISUALES`, `CINE`, `TEATRO`, `INFANTILES`,
`FERIAS`, `OTROS`.

**Modalidad de ingreso:** `INGRESO_LIBRE`, `ORDEN_DE_LLEGADA`, `RESERVA_PREVIA`.
Es el dato más accionable de la app: enterarse de que hacía falta reservar
cuando ya estás en la puerta llega tarde, así que la reserva previa se destaca
en la tarjeta y en la ficha.

**El `id` es determinista** (`slug(sede)-slug(título)-fecha`). Eso permite que
Room haga upsert sin duplicar filas y, sobre todo, que **los favoritos del
usuario sobrevivan a la actualización diaria**. Por lo mismo los favoritos
viven en una tabla aparte: la sincronización borra e inserta `events`, y si el
flag estuviera en esa fila se perdería cada mañana.

---

## 4. El bot de ingesta (Python)

```
scraper/
├── run_scraper.py            # CLI
├── requirements.txt
├── seed/                     # agenda curada a mano (red de seguridad)
├── tests/                    # 14 tests, corren sin red
└── eventos/
    ├── models.py             # Event / Venue + id determinista
    ├── normalize.py          # categoría, modalidad e horarios desde texto libre
    ├── venues.py             # catálogo de sedes + geocoding gratis (Nominatim)
    ├── pipeline.py           # dedupe, validación y escritura del JSON
    └── sources/
        ├── html_source.py    # JSON-LD primero, selectores CSS como plan B
        ├── palacio_libertad.py
        ├── usina_del_arte.py
        ├── ba_turismo.py
        └── local_seed.py
```

```bash
pip install -r scraper/requirements.txt
python scraper/run_scraper.py --days 7      # escribe docs/events.json
python scraper/run_scraper.py --offline     # sin red, solo seed local
python -m pytest scraper/tests -q
```

Decisiones que hacen que esto se mantenga solo:

- **JSON-LD antes que selectores CSS.** Las agendas oficiales corren sobre
  WordPress/Drupal y emiten `schema.org/Event` en un `<script type="application/ld+json">`.
  Ese marcado se rompe mucho menos que un `div.clase-que-cambia`. Los
  selectores CSS quedan como respaldo, declarados como atributos de cada
  subclase para retocarlos sin tocar el pipeline.
- **Una fuente caída no tumba la corrida.** `safe_fetch` atrapa la excepción,
  loguea y sigue con las demás.
- **Nunca se publica un JSON vacío.** El pipeline arrastra los eventos del
  archivo anterior y `refresh()` en la app rechaza un feed vacío: si todas las
  fuentes fallan, la agenda anterior sigue en pie.
- **Geocoding sin costo.** Las sedes se repiten, así que un catálogo local
  resuelve casi todo. Para una sede nueva se consulta Nominatim (OSM, gratis y
  sin API key), respetando su política de 1 req/s y cacheando el resultado en
  disco.
- **Dedupe por riqueza.** Un mismo evento aparece en varias agendas; gana la
  versión con más campos completos, para no perder la descripción o las
  coordenadas.

---

## 5. Puesta en marcha

### Backend gratuito (5 minutos)

1. Fork o push de este repo a un **repositorio público**.
2. **Settings → Pages → Source: GitHub Actions.**
   Este paso es manual sí o sí: el `GITHUB_TOKEN` del workflow no puede crear
   el sitio de Pages aunque tenga `pages: write` (la API de creación pide
   permisos de administración y devuelve *Resource not accessible by
   integration*). Una vez activado, el deploy es automático para siempre.
3. **Settings → Actions → General → Workflow permissions: Read and write.**
   (lo necesita el bot para commitear `docs/events.json`).
4. Pestaña **Actions → "Actualizar agenda de eventos" → Run workflow** para
   la primera corrida; de ahí en más va solo todos los días.

El feed queda en `https://<usuario>.github.io/<repo>/events.json`.

### App Android

Para solo usarla, alcanza con el [APK de la release](https://github.com/MagliLuc/eventos/releases/latest/download/agenda-gratis-ba.apk).
Para desarrollarla:

1. Abrir el proyecto en Android Studio (Ladybug o posterior) y sincronizar.
2. Poner tu URL en `app/build.gradle.kts`:

   ```kotlin
   buildConfigField("String", "EVENTS_FEED_URL", "\"https://<usuario>.github.io/<repo>/events.json\"")
   ```

3. `./gradlew assembleDebug` o Run.

```bash
./gradlew testDebugUnitTest   # tests de filtrado y de mapeo del feed
./gradlew assembleDebug       # el APK queda en app/build/outputs/apk/debug/
```

El workflow `android.yml` hace lo mismo en cada push a `main` y publica el APK
en la release `latest`. Es un build de depuración firmado con la clave de debug:
se instala y se usa sin problema, pero para Play Store hace falta un
`signingConfig` propio (ver `app/build.gradle.kts`).

---

## 6. Integraciones nativas (costo cero)

En vez de SDKs de terceros, se delega en las apps que el usuario ya tiene.
Todo en [`util/NativeIntents.kt`](app/src/main/java/ar/eventosba/util/NativeIntents.kt).

**Calendario** — `ACTION_INSERT` sobre `CalendarContract.Events.CONTENT_URI`.
No requiere los permisos `READ/WRITE_CALENDAR`: se abre el compositor con el
borrador cargado y el usuario confirma. Si la agenda no publicó hora de fin se
asume 2 h, que es la duración típica y evita un evento de duración cero.

**Navegación** — esquema `geo:lat,lon?q=lat,lon(Nombre)`. Es del sistema
operativo, no de un proveedor: funciona con Google Maps, OsmAnd, Organic Maps,
Waze o lo que el usuario tenga, sin consumir cuota de ninguna API.

**Compartir** — `ACTION_SEND` con `createChooser`.

Dos detalles que hacen que esto funcione en Android 11+:

- El bloque `<queries>` del manifest es obligatorio; sin él el sistema oculta
  las apps que resuelven estos Intents.
- Se atrapa `ActivityNotFoundException` en lugar de consultar
  `resolveActivity()`, que bajo la visibilidad de paquetes devuelve `null` de
  más y haría creer que no hay ninguna app instalada.

---

## 7. Mapa con OpenStreetMap

[`ui/map/OsmMap.kt`](app/src/main/java/ar/eventosba/ui/map/OsmMap.kt) embebe un
`MapView` de osmdroid en Compose vía `AndroidView`.

- El `MapView` se crea una sola vez con `remember`: recrearlo en cada
  recomposición tiraría la caché de tiles y los volvería a descargar.
- Un `DisposableEffect` conecta `onResume`/`onPause` al ciclo de vida. Sin eso
  osmdroid sigue bajando tiles con la app en segundo plano.
- El `User-Agent` se configura en `EventosApplication`: los servidores de tiles
  de OSM bloquean el default y el mapa quedaría gris.
- La atribución **© OpenStreetMap** se dibuja siempre sobre el mapa. No es
  decorativa: la licencia ODbL la exige.
- El mapa se encuadra automáticamente sobre los eventos filtrados, y comparte
  ViewModel con la lista (scopeado al back stack entry del grafo), así que los
  chips que aplicaste en la home siguen valiendo.

---

## 8. Stack

| Capa | Herramienta | Licencia |
|---|---|---|
| Lenguaje / UI | Kotlin 2.0 + Jetpack Compose + Material 3 | Apache 2.0 |
| Arquitectura | MVVM + ViewModel + StateFlow | Apache 2.0 |
| Persistencia | Room / SQLite | Apache 2.0 |
| Red | Retrofit + OkHttp + kotlinx.serialization | Apache 2.0 |
| Mapas | osmdroid + tiles de OpenStreetMap | Apache 2.0 / ODbL |
| Background | WorkManager | Apache 2.0 |
| Ingesta | Python + BeautifulSoup + lxml | MIT / BSD |
| Hosting + CI | GitHub Pages + GitHub Actions | gratis en repos públicos |

---

## 9. Datos y atribución

Los eventos provienen de agendas públicas oficiales (Palacio Libertad, Usina
del Arte, Centro Cultural Recoleta, Turismo Buenos Aires, argentina.gob.ar).
Cada evento conserva `source_name` y `source_url`, y la ficha enlaza a la
publicación original. La cartografía es © colaboradores de OpenStreetMap,
bajo ODbL.

El scraper se identifica con un User-Agent propio y hace un puñado de requests
por día: es un uso respetuoso de sitios públicos, no un crawler masivo. Antes
de agregar una fuente nueva conviene revisar sus términos y su `robots.txt`.
