package ar.eventosba.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.sourcesDataStore by preferencesDataStore(name = "source_prefs")

/**
 * Qué fuentes apagó el usuario en este teléfono.
 *
 * Se guardan las **apagadas** y no las encendidas a propósito: una fuente
 * nueva que aparezca en el feed tiene que verse sola, sin que el usuario la
 * tenga que ir a habilitar. Guardando las encendidas, cada fuente nueva
 * nacería invisible.
 *
 * Esto apaga la fuente **en la app**, no en el scraper: el scraper corre en
 * GitHub Actions y la app no puede editar su configuración. El panel lo
 * aclara para que no parezca que el interruptor no funcionó.
 */
class SourcePreferences(private val context: Context) {

    private val disabledKey = stringSetPreferencesKey("disabled_source_ids")

    val disabledIds: Flow<Set<String>> =
        context.sourcesDataStore.data.map { it[disabledKey] ?: emptySet() }

    suspend fun setEnabled(sourceId: String, enabled: Boolean) {
        context.sourcesDataStore.edit { prefs ->
            val current = prefs[disabledKey] ?: emptySet()
            prefs[disabledKey] = if (enabled) current - sourceId else current + sourceId
        }
    }

    /** Vuelve a mostrar todo. Es la salida del estado "apagué todo y no veo nada". */
    suspend fun enableAll() {
        context.sourcesDataStore.edit { it[disabledKey] = emptySet() }
    }
}
