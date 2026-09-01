package ar.eventosba.data.repository

import ar.eventosba.data.local.EventDao
import ar.eventosba.data.local.toDomain
import ar.eventosba.data.prefs.SyncPreferences
import ar.eventosba.data.remote.EventsApi
import ar.eventosba.data.remote.toEntity
import ar.eventosba.domain.model.Event
import ar.eventosba.domain.model.EventSource
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.LocalDate

/**
 * Unica fuente de verdad de la app.
 *
 * La UI observa siempre la base local (offline-first): la red solo empuja
 * datos hacia Room. Si la descarga falla, la pantalla no se entera y sigue
 * mostrando la ultima agenda valida.
 */
class EventRepository(
    private val dao: EventDao,
    private val api: EventsApi,
    private val prefs: SyncPreferences,
    private val feedUrl: String,
) {

    fun observeUpcoming(from: LocalDate = LocalDate.now()): Flow<List<Event>> =
        dao.observeUpcoming(from).map { rows -> rows.map { it.toDomain() } }

    fun observeFavorites(): Flow<List<Event>> =
        dao.observeFavorites().map { rows -> rows.map { it.toDomain() } }

    /** Estado de cada fuente segun la ultima corrida del scraper. */
    fun observeSources(): Flow<List<EventSource>> =
        dao.observeSources().map { rows -> rows.map { it.toDomain() } }

    fun observeEvent(id: String): Flow<Event?> =
        dao.observeById(id).map { it?.toDomain() }

    val lastSyncMillis: Flow<Long?> get() = prefs.lastSyncMillis

    suspend fun toggleFavorite(eventId: String) = dao.toggleFavorite(eventId)

    suspend fun hasCachedData(): Boolean = dao.count() > 0

    /**
     * Descarga el feed y reemplaza la cache.
     *
     * Devuelve un [Result] en vez de lanzar: quedarse sin internet es un
     * estado esperado en esta app, no una excepcion.
     */
    suspend fun refresh(): Result<Int> = runCatching {
        val feed = api.getEvents(feedUrl)
        val entities = feed.events.mapNotNull { it.toEntity() }
        // Un feed vacio casi siempre es un error de la fuente, no un dia sin
        // eventos: en ese caso conservamos lo que ya teniamos.
        if (entities.isEmpty()) {
            error("El feed llegó vacío; se conserva la agenda en caché.")
        }
        dao.replaceAll(entities, LocalDate.now())
        dao.replaceSources(feed.sources.map { it.toEntity() })
        prefs.recordSync(feed.generatedAt)
        entities.size
    }
}
