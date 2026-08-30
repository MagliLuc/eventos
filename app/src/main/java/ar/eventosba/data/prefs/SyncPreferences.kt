package ar.eventosba.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "sync_prefs")

/** Metadatos de la ultima sincronizacion. Sirven para el cartel de "offline". */
class SyncPreferences(private val context: Context) {

    private val lastSyncKey = longPreferencesKey("last_sync_millis")
    private val generatedAtKey = stringPreferencesKey("feed_generated_at")

    val lastSyncMillis: Flow<Long?> =
        context.dataStore.data.map { it[lastSyncKey] }

    val feedGeneratedAt: Flow<String?> =
        context.dataStore.data.map { it[generatedAtKey] }

    suspend fun recordSync(generatedAt: String?) {
        context.dataStore.edit { prefs ->
            prefs[lastSyncKey] = System.currentTimeMillis()
            generatedAt?.let { prefs[generatedAtKey] = it }
        }
    }
}
