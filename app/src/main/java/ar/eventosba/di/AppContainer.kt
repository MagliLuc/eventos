package ar.eventosba.di

import android.content.Context
import ar.eventosba.BuildConfig
import ar.eventosba.data.local.EventDatabase
import ar.eventosba.data.prefs.SourcePreferences
import ar.eventosba.data.prefs.SyncPreferences
import ar.eventosba.data.remote.NetworkModule
import ar.eventosba.data.repository.EventRepository

/**
 * Inyeccion de dependencias a mano.
 *
 * Para un grafo de este tamaño (una base, un cliente HTTP, un repositorio),
 * Hilt agregaria procesamiento de anotaciones y tiempo de build sin dar nada
 * a cambio. Todo se crea `by lazy`, asi que nada se instancia hasta que se usa.
 */
class AppContainer private constructor(context: Context) {

    private val appContext = context.applicationContext

    private val database by lazy { EventDatabase.get(appContext) }
    private val api by lazy { NetworkModule.eventsApi(appContext) }
    private val syncPreferences by lazy { SyncPreferences(appContext) }

    /** Que fuentes apago el usuario. Lo comparten la home y el panel. */
    val sourcePreferences: SourcePreferences by lazy { SourcePreferences(appContext) }

    val eventRepository: EventRepository by lazy {
        EventRepository(
            dao = database.eventDao(),
            api = api,
            prefs = syncPreferences,
            feedUrl = BuildConfig.EVENTS_FEED_URL,
        )
    }

    companion object {
        @Volatile
        private var instance: AppContainer? = null

        fun from(context: Context): AppContainer =
            instance ?: synchronized(this) {
                instance ?: AppContainer(context).also { instance = it }
            }
    }
}
